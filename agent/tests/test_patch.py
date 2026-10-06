"""Patch policy and template tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from raphael_agent.graph.nodes import node_patch
from raphael_agent.patch import propose_patch
from raphael_agent.patch.policy import apply_policy, check_patch_policy, path_allowed
from raphael_agent.patch.templates import TemplateRefusal, fix_bad_image, fix_missing_configmap_key, fix_probe_port_mismatch
from raphael_agent.schema_util import validate_agent

REPO = Path(__file__).resolve().parents[2]
PROBE_WS = REPO / "agent" / "fixtures" / "scenarios" / "probe_port_mismatch"


def test_path_allowlist():
    assert path_allowed("deploy/manifests/app.yaml")
    assert path_allowed(".github/workflows/deploy.yml")
    assert not path_allowed("src/main.go")
    assert not path_allowed("secrets/prod.env")


def test_policy_rejects_secret_like():
    proposal = {
        "files": [
            {
                "path": "deploy/app.yaml",
                "action": "modify",
                "content": "api_key: SUPERSECRETVALUE123\n",
            }
        ]
    }
    violations = check_patch_policy(proposal)
    assert any(v["rule"] == "secret_like_content" for v in violations)


def test_policy_rejects_privilege():
    proposal = {
        "files": [
            {
                "path": "deploy/app.yaml",
                "action": "modify",
                "content": "securityContext:\n  privileged: true\n",
            }
        ]
    }
    violations = check_patch_policy(proposal)
    assert any(v["rule"] == "privilege_escape" for v in violations)


def test_propose_probe_fix_minimal(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    run = {
        "workspace_path": str(PROBE_WS),
        "manifests": {
            "type": "yaml",
            "path": "deploy/manifests",
            "fixed_path": "deploy/manifests_fixed",
        },
        "evidence": [{"evidence_id": "ev-1"}],
        "attempt_count": {"diagnosis": 1, "patch": 0},
        "failure_signature": _probe_signature(),
        "diagnosis": {
            "selected_hypothesis_id": "hyp-probe-port",
            "classification": {
                "category": "supported",
                "failure_class": "probe_misconfiguration",
            },
        },
    }
    proposal = propose_patch(run)
    validate_agent("patch_proposal.json", proposal)
    assert proposal["policy_status"] == "allowed"
    assert proposal["sandbox_deploy_hint"]["use_files_as_patch"] is True
    contents = "\n".join(f.get("content") or "" for f in proposal["files"])
    assert "port: 8080" in contents
    assert "port: 9090" not in contents.split("readinessProbe:")[-1]


def _probe_signature(name="payments-api", container="app"):
    return {"class": "probe_misconfiguration", "key": f"probe_port_mismatch:{name}:8080!=9090",
            "normalized": {"reason": "ReadinessProbePortMismatch", "resource_kind": "Deployment",
                           "resource_name": name, "container": container,
                           "attributes": {"container_port": 8080, "probe_port": 9090}}}


def _image_signature(name="target", container="app"):
    image = "ghcr.io/acme/app:does-not-exist"
    return {"class": "bad_image_reference", "key": "image_pull:" + json.dumps(["Deployment", name, "regular", container, image, "not_found"], separators=(",", ":")),
            "normalized": {"reason": "ImagePullBackOff", "resource_kind": "Deployment",
                           "resource_name": name, "container": container, "attributes": {"image": image, "image_pull_cause": "not_found", "evidence_source": "runtime", "owner_verified": True, "container_type": "regular"}}}


def _image_run(signature, rendered_files):
    return {
        "failure_signature": signature,
        "rendered_files": rendered_files,
        "repository": {"owner": "acme", "name": "app"},
        "localization_result": {
            "service_name": "target",
            "environment": "staging",
            "approved_image_replacement": {
                "image": "ghcr.io/acme/app@sha256:" + "a" * 64,
                "resource_name": "target",
                "container_name": "app",
                "source": {
                    "kind": "verified_healthy_trace",
                    "healthy_trace_id": "healthy-1",
                    "source_commit_sha": "b" * 40,
                    "repository": "acme/app",
                    "service_name": "target",
                    "environment": "staging",
                },
            },
        },
    }


def _config_signature(name="target", container="app"):
    return {"class": "invalid_missing_config", "key": "missing_configmap_key:target-config:DATABASE_URL",
            "normalized": {"reason": "CreateContainerConfigError", "resource_kind": "Deployment",
                           "resource_name": name, "container": container,
                           "attributes": {"configmap": "target-config", "key": "DATABASE_URL"}}}


def _rendered(content):
    return [{"path": "deploy/manifests/app.yaml", "content": content}]


def test_probe_changes_only_signature_target_in_multi_deployment_file():
    first = """kind: Deployment
metadata:
  name: unrelated
spec:
  template:
    spec:
      containers:
      - name: app
        ports:
        - containerPort: 8000
        readinessProbe:
          httpGet:
            port: 9000
"""
    target = first.replace("unrelated", "payments-api").replace("8000", "8080").replace("9000", "9090")
    files = fix_probe_port_mismatch({"failure_signature": _probe_signature(), "rendered_files": _rendered(first + "---\n" + target)})
    assert files is not None and len(files) == 1
    assert files[0]["content"].split("---\n", 1)[0] == first
    assert "port: 9000" in files[0]["content"]
    assert "port: 9090" not in files[0]["content"]
    assert "port: 8080" in files[0]["content"]


def test_image_changes_only_signature_target_in_multi_deployment_file():
    target = """kind: Deployment
metadata:
  name: target
spec:
  template:
    spec:
      containers:
      - name: app
        image: ghcr.io/acme/app:does-not-exist
"""
    unrelated = target.replace("name: target", "name: unrelated")
    files = fix_bad_image(_image_run(_image_signature(), _rendered(unrelated + "---\n" + target)))
    assert files is not None and len(files) == 1
    assert files[0]["content"].split("---\n", 1)[0] == unrelated
    assert files[0]["content"].count("ghcr.io/acme/app:does-not-exist") == 1
    assert files[0]["content"].count("ghcr.io/acme/app@sha256:" + "a" * 64) == 1


def test_image_patch_refuses_without_healthy_release_provenance():
    target = """kind: Deployment
metadata:
  name: target
spec:
  template:
    spec:
      containers:
      - name: app
        image: ghcr.io/acme/app:does-not-exist
"""
    run = _image_run(_image_signature(), _rendered(target))
    run["localization_result"].pop("approved_image_replacement")

    with pytest.raises(TemplateRefusal) as error:
        fix_bad_image(run)

    assert error.value.reason == "patch_value_unavailable"


@pytest.mark.parametrize("template,signature", [
    (fix_probe_port_mismatch, _probe_signature),
    (fix_bad_image, _image_signature),
])
def test_ambiguous_duplicate_resource_refuses(template, signature):
    name = "payments-api" if template is fix_probe_port_mismatch else "target"
    content = f"kind: Deployment\nmetadata:\n  name: {name}\n---\nkind: Deployment\nmetadata:\n  name: {name}\n"
    with pytest.raises(TemplateRefusal, match="Expected one Deployment") as error:
        run = _image_run(signature(), _rendered(content)) if template is fix_bad_image else {
            "failure_signature": signature(), "rendered_files": _rendered(content)
        }
        template(run)
    assert error.value.reason == "patch_target_unavailable"


def test_pod_only_image_signature_refuses_without_owner_mapping():
    signature = _image_signature()
    signature["normalized"]["resource_kind"] = "Pod"
    with pytest.raises(TemplateRefusal) as error:
        fix_bad_image({"failure_signature": signature, "rendered_files": _rendered("kind: Deployment\nmetadata:\n  name: target\n")})
    assert error.value.reason == "patch_target_unavailable"


def test_liveness_too_early_is_not_mispatched_as_readiness_port_mismatch():
    signature = _probe_signature()
    signature["normalized"]["reason"] = "LivenessProbeTooEarly"
    with pytest.raises(TemplateRefusal) as error:
        fix_probe_port_mismatch({"failure_signature": signature, "rendered_files": _rendered("kind: Deployment\n")})
    assert error.value.reason == "patch_target_unavailable"


@pytest.mark.parametrize("template", [fix_probe_port_mismatch, fix_bad_image, fix_missing_configmap_key])
@pytest.mark.parametrize("signature", [None, "generic", {"normalized": "not-a-map"}, {"normalized": {"attributes": "not-a-map"}}])
def test_missing_or_malformed_structural_signature_refuses(template, signature):
    with pytest.raises(TemplateRefusal) as error:
        template({"failure_signature": signature, "rendered_files": _rendered("kind: Deployment\n")})
    assert error.value.reason == "patch_target_unavailable"


def test_shared_yaml_alias_refuses_instead_of_changing_another_container():
    content = """kind: Deployment
metadata:
  name: target
spec:
  template:
    spec:
      containers:
      - name: app
        image: &bad ghcr.io/acme/app:does-not-exist
      - name: sidecar
        image: *bad
"""
    with pytest.raises(TemplateRefusal, match="shared by a YAML alias"):
        fix_bad_image(_image_run(_image_signature(), _rendered(content)))


def test_configmap_exact_target_still_refuses_unevidenced_value():
    content = """kind: ConfigMap
metadata:
  name: unrelated
data:
  LOG_LEVEL: info
---
kind: ConfigMap
metadata:
  name: target-config
data:
  LOG_LEVEL: info
---
kind: Deployment
metadata:
  name: target
spec:
  template:
    spec:
      containers:
      - name: app
        env:
        - name: DATABASE_URL
          valueFrom:
            configMapKeyRef:
              name: target-config
              key: DATABASE_URL
"""
    original = content.encode("utf-8")
    run = {"failure_signature": _config_signature(), "rendered_files": _rendered(content)}
    with pytest.raises(TemplateRefusal) as error:
        fix_missing_configmap_key(run)
    assert error.value.reason == "patch_value_unavailable"
    assert run["rendered_files"][0]["content"].encode("utf-8") == original
    assert content.split("---\n", 1)[0] == """kind: ConfigMap
metadata:
  name: unrelated
data:
  LOG_LEVEL: info
"""


def test_duplicate_configmap_target_refuses_before_value_selection():
    configmap = "kind: ConfigMap\nmetadata:\n  name: target-config\ndata:\n  LOG_LEVEL: info\n"
    deployment = """kind: Deployment
metadata:
  name: target
spec:
  template:
    spec:
      containers:
      - name: app
        env:
        - name: DATABASE_URL
          valueFrom:
            configMapKeyRef:
              name: target-config
              key: DATABASE_URL
"""
    with pytest.raises(TemplateRefusal, match="Expected one ConfigMap/target-config, found 2") as error:
        fix_missing_configmap_key({"failure_signature": _config_signature(),
                                   "rendered_files": _rendered(configmap + "---\n" + configmap + "---\n" + deployment)})
    assert error.value.reason == "patch_target_unavailable"


@pytest.mark.parametrize("failure_class,signature,expected_reason", [
    ("probe_misconfiguration", None, "patch_target_unavailable"),
    ("bad_image_reference", None, "patch_target_unavailable"),
    ("invalid_missing_config", None, "patch_target_unavailable"),
    ("invalid_missing_config", _config_signature(), "patch_value_unavailable"),
])
def test_refusal_is_terminal_and_never_submits_empty_patch(monkeypatch, failure_class, signature, expected_reason):
    monkeypatch.setenv("RAPHAEL_LLM_PATCH", "0")
    from raphael_agent.graph.state import initial_run_state

    state = initial_run_state({"run_id": "test-refusal", "tenant_id": "test", "trigger": {"kind": "github_workflow_run"},
                               "repository": {"owner": "x", "name": "y"}, "commit_sha": "a" * 40}, sandbox_mode="recorded_stub")
    state["status"] = "running"
    state["fix_rules"] = {"source": "test"}
    state["reproduction_result"] = {"reproduced": True}
    state["diagnosis"] = {"selected_hypothesis_id": "h", "classification": {"failure_class": failure_class}, "hypotheses": []}
    state["failure_signature"] = signature or {"class": failure_class, "key": "generic", "normalized": {"resource_kind": "Pod", "resource_name": "pod"}}
    state["rendered_files"] = _rendered("""kind: ConfigMap
metadata:
  name: target-config
data:
  LOG_LEVEL: info
---
kind: Deployment
metadata:
  name: target
spec:
  template:
    spec:
      containers:
      - name: app
        env:
        - name: DATABASE_URL
          valueFrom:
            configMapKeyRef:
              name: target-config
              key: DATABASE_URL
""")
    updates = node_patch(state)
    assert updates["status"] == "escalated"
    assert updates["terminal_reason"] == expected_reason
    assert updates["escalation_report"]["reason_code"] == expected_reason
    assert "candidate_patches" not in updates
    assert "active_patch_id" not in updates


@pytest.mark.parametrize("failure_class,signature", [
    ("probe_misconfiguration", _probe_signature),
    ("bad_image_reference", _image_signature),
])
def test_ambiguous_target_reaches_explicit_terminal_without_patch(monkeypatch, failure_class, signature):
    from raphael_agent.graph.state import initial_run_state

    monkeypatch.setenv("RAPHAEL_LLM_PATCH", "0")
    name = "payments-api" if failure_class == "probe_misconfiguration" else "target"
    state = initial_run_state({"run_id": "ambiguous", "tenant_id": "test", "trigger": {"kind": "github_workflow_run"},
                               "repository": {"owner": "x", "name": "y"}, "commit_sha": "a" * 40}, sandbox_mode="recorded_stub")
    state.update({
        "status": "running", "fix_rules": {"source": "test"},
        "reproduction_result": {"reproduced": True},
        "diagnosis": {"selected_hypothesis_id": "h", "classification": {"failure_class": failure_class}, "hypotheses": []},
        "failure_signature": signature(),
        "rendered_files": _rendered(f"kind: Deployment\nmetadata:\n  name: {name}\n---\nkind: Deployment\nmetadata:\n  name: {name}\n"),
    })
    updates = node_patch(state)
    assert updates["status"] == "escalated"
    assert updates["terminal_reason"] == "patch_target_unavailable"
    assert updates["escalation_report"]["reason_code"] == "patch_target_unavailable"
    assert "candidate_patches" not in updates


def test_apply_policy_sets_rejected():
    proposal = {
        "patch_id": "p1",
        "attempt": 1,
        "hypothesis_id": "h",
        "files": [{"path": "evil/bin.sh", "action": "modify", "content": "echo hi\n"}],
        "rationale": {"summary": "x", "evidence_ids": []},
        "policy_status": "pending",
        "created_at": "2026-08-10T12:00:00Z",
    }
    updated = apply_policy(proposal)
    assert updated["policy_status"] == "rejected"
