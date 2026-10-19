"""Hosted-only real repair proof with production hooks and a scoped catalog fixture."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from datetime import datetime, timedelta, timezone
import uuid

from cluster import CONTEXT, kube, pods, ready, wait_for, cleanup_namespace
from run_real_job import trace_records

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evals.run_evals import trace_evidence, patch_line_changes
from raphael_agent.image_pull import image_pull_repair_allowed

REQUIRED_KIND_CASES = ("probe", "image-without-provenance", "image-with-verified-provenance", "healthy-sentinel")


class CatalogFixture:
    """Loopback REST fixture, not live Supabase ingestion or an AgentHooks override."""
    def __init__(self, baseline):
        self.baseline = baseline
        self.requests = []
        fixture = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                path = urlsplit(self.path)
                query = parse_qs(path.query)
                fixture.requests.append({"path": path.path, "query": query})
                rows = []
                if path.path.endswith("/raphael_clients") and query.get("client_id") == ["eq.proof-client"]:
                    rows = [{"client_id": "proof-client", "company_id": "proof-company", "client_name": "kind-proof"}]
                elif path.path.endswith("/raphael_healthy_traces") and all(
                    query.get(key) == ["eq." + baseline[key]]
                    for key in ("company_id", "client_id", "service_name", "environment")
                ):
                    rows = [baseline]
                body = json.dumps(rows).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                # Outcome telemetry is best effort; no real backend is configured.
                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"[]")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}"


def commit_fixture(source, destination):
    shutil.copytree(source, destination)
    for args in (["git", "init"], ["git", "add", "."],
                 ["git", "-c", "user.name=Fixture CI", "-c", "user.email=fixture@example.invalid",
                  "commit", "-m", "Versioned synthetic kind fixture"]):
        subprocess.run(args, cwd=destination, check=True, capture_output=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=destination, text=True).strip()


def verify_case(label, result, records, initial_pod, final_ready):
    state = result["run_state"]
    evidence = trace_evidence(records, result["job_id"])
    if label == "healthy-sentinel":
        assert ready(initial_pod), "healthy sentinel control was not Ready"
        assert state.get("sandbox_backend") not in {None, "", "mock"}
        assert evidence["observed_signature"]["class"] == "healthy"
        assert evidence["observed_signature"]["reproduced"] is False
        assert result["final_status"] == "escalated" and state["terminal_reason"] == "low_confidence"
        assert not state.get("candidate_patches") and not state.get("pull_request_url")
        assert not evidence["patch_files"] and evidence["validation"] is None
        assert result["terminal"]["payload"]["instructions"] == "discard_local_copy"
        return
    assert not ready(initial_pod), "failure control was already Ready"
    expected_class = "probe_misconfiguration" if label == "probe" else "bad_image_reference"
    assert evidence["observed_signature"]["class"] == expected_class
    assert evidence["observed_signature"]["reproduced"] is True
    assert result["terminal"]["payload"]["instructions"] == "discard_local_copy"
    if state.get("pull_request_url"):
        assert state.get("publish", {}).get("dry_run") is True
        assert "/compare/" in state["pull_request_url"] and "raphael_dry_run=1" in state["pull_request_url"]
    if label != "probe":
        signature = evidence["observed_signature"]
        assert state.get("sandbox_backend") not in {None, "", "mock"}
        assert signature["normalized"]["attributes"]["evidence_source"] == "runtime"
        assert image_pull_repair_allowed(signature, state["sandbox_backend"])
    if label == "image-without-provenance":
        assert result["final_status"] == "escalated"
        assert not state.get("pull_request_url")
        assert state["terminal_reason"] == "patch_value_unavailable"
        assert not (state.get("localization_result") or {}).get("approved_image_replacement")
        assert not state.get("candidate_patches") and not evidence["patch_files"]
        assert evidence["validation"] is None
        return
    assert result["final_status"] == "fix_finalized"
    assert final_ready, "no independently observed post-patch Ready Pod"
    assert evidence["validation"]["passed"] is True and evidence["validation"]["signature_cleared"] is True
    assert state["publish"]["dry_run"] is True
    assert len(evidence["patch_files"]) == 1
    assert evidence["patch_files"][0]["path"] == "deploy/manifests/app.yaml"
    count, changed = patch_line_changes(evidence["patch_files"], evidence["initial_rendered_files"])
    if label == "probe":
        assert count == 2 and {line[1:].strip() for line in changed} == {"port: 9090", "port: 8080"}, changed
    else:
        assert count == 2 and all("image:" in line for line in changed), changed
        approved = state["localization_result"]["approved_image_replacement"]
        assert approved["source"]["healthy_trace_id"] == "kind-verified-baseline"
        assert approved["image"] == "hashicorp/http-echo:1.0"


def verify_workload_identity(pod, replica_sets, deployments, signature, namespace):
    """Bind a current Pod to the exact observed Deployment and regular container."""
    metadata = pod["metadata"]
    assert metadata["namespace"] == namespace
    assert metadata["uid"]
    owners = [o for o in metadata.get("ownerReferences", []) if o.get("controller") and o.get("kind") == "ReplicaSet"]
    assert len(owners) == 1
    owner = owners[0]
    rs = next(x for x in replica_sets["items"] if x["metadata"]["name"] == owner["name"] and x["metadata"]["uid"] == owner["uid"] and x["metadata"]["namespace"] == namespace)
    owners = [o for o in rs["metadata"].get("ownerReferences", []) if o.get("controller") and o.get("kind") == "Deployment"]
    assert len(owners) == 1
    owner = owners[0]
    deployment = next(x for x in deployments["items"] if x["metadata"]["name"] == owner["name"] and x["metadata"]["uid"] == owner["uid"] and x["metadata"]["namespace"] == namespace)
    normalized = signature["normalized"]
    assert normalized["resource_kind"] == "Deployment" and normalized["resource_name"] == deployment["metadata"]["name"]
    container = next(c for c in pod["spec"]["containers"] if c["name"] == normalized["container"])
    assert container["image"] == normalized["attributes"]["image"]
    return {"namespace": namespace, "pod_uid": metadata["uid"], "replica_set_uid": rs["metadata"]["uid"],
            "deployment_uid": deployment["metadata"]["uid"], "container": container["name"], "image": container["image"]}


def install_rollout_wrapper(out, real_kubectl):
    rollout_pids = out / "rollout-pids"
    bin_dir = out / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "kubectl"
    wrapper.write_text(f"#!{sys.executable}\nimport os, sys\n"
                       f"if 'rollout' in sys.argv and 'status' in sys.argv:\n"
                       f"    sys.argv[sys.argv.index('--timeout') + 1] = '30s'\n"
                       f"    with open({str(rollout_pids)!r}, 'a') as stream: stream.write(str(os.getpid()) + '\\n')\n"
                       f"os.execv({real_kubectl!r}, [{real_kubectl!r}] + sys.argv[1:])\n")
    wrapper.chmod(0o755)
    return bin_dir


def run_case(label, fixture, sha, output, catalog=None):
    out = output / label
    out.mkdir(parents=True)
    gate, trace, result_path = out / "release", out / "trace.jsonl", out / "runner-result.json"
    env = dict(os.environ)
    rollout_pids = out / "rollout-pids"
    if label == "image-without-provenance":
        # The wrapper execs the real kubectl at the same PID; no rollout response
        # is mocked. Force the CLI timeout to 30s so a native short timeout cannot
        # masquerade as process cancellation. Only controller children use this PATH.
        real_kubectl = shutil.which("kubectl")
        assert real_kubectl
        bin_dir = install_rollout_wrapper(out, real_kubectl)
        env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY", "RAPHAEL_SECRET_FIXTURE_SET",
                "GITHUB_TOKEN", "RAPHAEL_GITHUB_TOKEN", "RAPHAEL_GITHUB_APP_PRIVATE_KEY",
                "RAPHAEL_GITHUB_APP_PRIVATE_KEY_PATH", "RAPHAEL_GITHUB_APP_ID", "RAPHAEL_GITHUB_INSTALLATION_ID"):
        env.pop(key, None)
    env.update({"E2E_CLUSTER_BACKEND": "kind", "E2E_KUBE_CONTEXT": CONTEXT,
                "E2E_IGNIS_BIN": os.environ["E2E_IGNIS_BIN"], "E2E_REAL_CLONE_URL": fixture.as_uri(),
                "E2E_REAL_COMMIT_SHA": sha, "E2E_REAL_NARROWED_LOCATION": "deploy/manifests/app.yaml",
                "E2E_REAL_RESULT_FILE": str(result_path), "E2E_TRACE_FILE": str(trace),
                "E2E_REAL_DISPATCH_LOG": str(out / "dispatch.log"), "E2E_REAL_IGNIS_LOG": str(out / "ignis.log"),
                "E2E_INSPECT_GATE": str(gate), "E2E_REAL_LEASE_TTL_SECONDS": "600", "E2E_REAL_TIMEOUT_SECONDS": "300",
                "RAPHAEL_CONNECTOR_HTTP_TIMEOUT_SECONDS": "240", "RAPHAEL_MAX_WALL_SECONDS": "600",
                "RAPHAEL_LLM_DIAGNOSIS": "0", "RAPHAEL_LLM_PATCH": "0", "RAPHAEL_MODEL_ENABLED": "0",
                "RAPHAEL_LEARNING": "0", "RAPHAEL_PARTNER_MODE": "dry_run", "RAPHAEL_PUBLISH_MODE": "dry_run"})
    if label == "probe":
        env["RAPHAEL_SECRET_FIXTURE_SET"] = "payments-test"
    if catalog:
        env.update(SUPABASE_URL=catalog.url, SUPABASE_SERVICE_ROLE_KEY="synthetic-catalog-key",
                   RAPHAEL_CLIENT_ID="proof-client", RAPHAEL_COMPANY_ID="proof-company",
                   RAPHAEL_DEFAULT_ENVIRONMENT="kind-proof")
    namespace = None
    owned = set()
    snapshots = []
    with (out / "runner.log").open("w") as log:
        process = subprocess.Popen([sys.executable, str(ROOT / "e2e/run_real_job.py")], cwd=ROOT,
                                   env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            received = gate.with_suffix(".received.json")
            wait_for(received.exists, "initial deployed workload at inspection barrier", timeout=120)
            body = json.loads(received.read_text())
            deployment_result = body["payload"]["result"]
            sandbox = body["payload"]["result"]["sandbox_id"]
            records = trace_records(trace)
            created = next(body["payload"]["result"] for row in records
                           if (body := json.loads(row["request"]["body"] or "{}"))
                           and body.get("payload", {}).get("verb") == "create_sandbox"
                           and body["payload"].get("status") == "ok")
            if label == "probe":
                coverage = deployment_result["fidelity"]["secret_coverage"]
                assert coverage["complete"] and not coverage["truncated"], coverage
                assert len(coverage["references"]) == 1, coverage
                reference = coverage["references"][0]
                assert reference["secret_name"] == "payments-db" and reference["key"] == "DATABASE_URL"
                assert reference["status"] == "covered", coverage
            namespace = created["namespace"]
            assert created["cluster_backend"] != "mock"
            owned.add(namespace)
            def failed_pod():
                for pod in pods(namespace):
                    if label == "healthy-sentinel":
                        if ready(pod):
                            return pod
                        continue
                    if ready(pod):
                        continue
                    if label == "probe":
                        events = kube("get", "events", "-n", namespace, "-o", "json")
                        if "Readiness probe failed" in events:
                            return pod
                    elif any(item.get("state", {}).get("waiting", {}).get("reason") in
                             {"ErrImagePull", "ImagePullBackOff"}
                             for item in pod.get("status", {}).get("containerStatuses", [])):
                        return pod
            initial = wait_for(failed_pod, "independent Kubernetes failure")
            (out / "initial-pod.json").write_text(json.dumps(initial, indent=2))
            (out / "initial-events.json").write_text(kube("get", "events", "-n", namespace, "-o", "json"))
            replica_sets = json.loads(kube("get", "replicasets", "-n", namespace, "-o", "json"))
            deployments = json.loads(kube("get", "deployments", "-n", namespace, "-o", "json"))
            (out / "initial-replicasets.json").write_text(json.dumps(replica_sets, indent=2))
            (out / "initial-deployments.json").write_text(json.dumps(deployments, indent=2))
            if label == "image-without-provenance":
                verify_rollout_deadline(sandbox, rollout_pids, out)
            gate.touch()
            deadline = time.monotonic() + 240
            while not result_path.exists():
                assert process.poll() is None, "runner exited before producing a result"
                assert time.monotonic() < deadline, "runner outcome timeout"
                snapshots.extend(pods(namespace))
                time.sleep(0.1)
            result = json.loads(result_path.read_text())
            assert process.wait(timeout=20) == 0
            records = trace_records(trace)
            verify_case(label, result, records, initial, any(ready(pod) for pod in snapshots))
            if label == "probe":
                assert result["run_state"]["secret_coverage"] == coverage

            if label in {"image-without-provenance", "image-with-verified-provenance"}:
                identity = verify_workload_identity(initial, replica_sets, deployments, trace_evidence(records, result["job_id"])["observed_signature"], namespace)
                (out / "verified-workload-identity.json").write_text(json.dumps(identity, indent=2))
            if catalog:
                approved = result["run_state"]["localization_result"]["approved_image_replacement"]
                for field in ("source_commit_sha", "repository", "service_name", "environment"):
                    assert approved["source"][field] == catalog.baseline[field]
            (out / "proof.json").write_text(json.dumps({"passed": True, "case": label, "fixture_commit": sha,
                                                       "raphael_revision": os.getenv("GITHUB_SHA"),
                                                       "sandbox_id": sandbox, "namespace": namespace,
                                                       "initial_pod": initial, "ready_observed": any(ready(p) for p in snapshots)}, indent=2))
            print(f"PASS {label}", flush=True)
        finally:
            gate.touch()
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            (out / "pod-observations.json").write_text(json.dumps(snapshots, indent=2))
            if namespace:
                cleanup_namespace(namespace, owned)


def verify_rollout_deadline(sandbox, pid_file, output):
    """A real failing workload keeps real kubectl busy beyond an 8-second deadline."""
    action_id = "owned-rollout-deadline-" + uuid.uuid4().hex
    absolute = (datetime.now(timezone.utc) + timedelta(seconds=8)).isoformat()
    request = Request(f"http://127.0.0.1:8090/v1/sandboxes/{sandbox}/validate", method="POST",
                      data=json.dumps({"plan": {"commands": [], "health_checks": [
                          {"type": "rollout", "resource": "deployment/payments-api", "mandatory": True, "timeout_seconds": 30}]}}).encode(),
                      headers={"Content-Type": "application/json", "x-raphael-action-deadline-at": absolute,
                               "x-raphael-connector-action-id": action_id})
    start = time.monotonic()
    status, body = None, None
    try:
        with urlopen(request, timeout=15) as response:
            status, body = response.status, json.load(response)
    except HTTPError as error:
        status, body = error.code, json.loads(error.read())
    elapsed = time.monotonic() - start
    (output / "rollout-deadline-response.json").write_text(json.dumps({"status": status, "body": body, "elapsed_seconds": elapsed}, indent=2))
    assert status == 504, (status, body)
    assert 6 < elapsed < 12, elapsed
    assert pid_file.exists(), "real kubectl rollout never started; timeout alone is insufficient proof"
    pids = [int(pid) for pid in pid_file.read_text().splitlines()]
    assert pids
    def stopped():
        for pid in pids:
            path = Path(f"/proc/{pid}/stat")
            if path.exists() and path.read_text().split()[2] != "Z":
                return False
        return True
    wait_for(stopped, "real kubectl cancellation", timeout=3)
    (output / "rollout-deadline-proof.json").write_text(json.dumps({
        "passed": True, "backend": "kind", "command": "real kubectl rollout status deployment/payments-api",
        "action_id": action_id, "http_status": status, "elapsed_seconds": elapsed,
        "kubectl_processes_stopped": True, "configured_rollout_seconds": 30, "absolute_budget_seconds": 8, "owned_wrapper_cli_timeout_seconds": 30}, indent=2))


def selected_cases():
    """All released-pair controls are required for every supported CI event."""
    return REQUIRED_KIND_CASES


def main():
    assert os.getenv("GITHUB_ACTIONS") == "true", "hosted disposable CI only"
    cases = selected_cases()
    assert kube("config", "current-context").strip() == CONTEXT
    output = ROOT / "e2e/kind-remediation-out"
    output.mkdir(exist_ok=True)
    (output / "cluster-version.json").write_text(kube("version", "-o", "json"))
    owned = set()
    namespace = "raphael-remediation-baseline-" + uuid.uuid4().hex[:8]
    try:
        with tempfile.TemporaryDirectory(prefix="remediation-source-") as temp:
            source = Path(temp) / "proof-source"
            source.mkdir()
            shas = {name: commit_fixture(ROOT / "e2e/fixtures/kind-remediation" / name, source / name)
                    for name in ("probe", "bad-image", "healthy", "healthy-sentinel")}
            kube("create", "namespace", namespace)
            owned.add(namespace)
            kube("apply", "-n", namespace, "-f", str(source / "healthy/deploy/manifests/app.yaml"))
            healthy = wait_for(lambda: next((pod for pod in pods(namespace) if ready(pod)), None), "verified healthy baseline")
            assert healthy["spec"]["containers"][0]["image"] == "hashicorp/http-echo:1.0"
            assert healthy["status"]["containerStatuses"][0]["imageID"]
            baseline = {"healthy_trace_id": "kind-verified-baseline", "company_id": "proof-company",
                        "client_id": "proof-client", "service_name": "raphael-e2e-fixture", "environment": "kind-proof",
                        "repository": "proof-source/raphael-e2e-fixture", "verified_healthy": True,
                        "is_last_known_good": True, "source_commit_sha": shas["healthy"],
                        "runtime_identity": {"resource_kind": "Deployment", "resource_name": "payments-api",
                                             "container_images": {"api": "hashicorp/http-echo:1.0"}}}
            (output / "baseline.json").write_text(json.dumps({"catalog_row": baseline, "ready_pod": healthy}, indent=2))
            for label in cases:
                if label == "probe":
                    run_case(label, source / "probe", shas["probe"], output)
                elif label == "healthy-sentinel":
                    run_case(label, source / "healthy-sentinel", shas["healthy-sentinel"], output)
                elif label == "image-without-provenance":
                    run_case(label, source / "bad-image", shas["bad-image"], output)
                else:
                    with CatalogFixture(baseline) as catalog:
                        run_case(label, source / "bad-image", shas["bad-image"], output, catalog)
                        (output / "catalog-requests.json").write_text(json.dumps(catalog.requests, indent=2))
    finally:
        if namespace in owned:
            cleanup_namespace(namespace, owned)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
