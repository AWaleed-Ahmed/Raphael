"""Deterministic fix templates for high-confidence known patterns (FR-045)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode


class TemplateRefusal(Exception):
    """A deterministic template cannot justify a safe patch."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


def _field(node: Node | None, name: str) -> Node | None:
    if not isinstance(node, MappingNode):
        return None
    matches = [value for key, value in node.value if isinstance(key, ScalarNode) and key.value == name]
    return matches[0] if len(matches) == 1 else None


def _at(node: Node | None, *path: str) -> Node | None:
    for part in path:
        node = _field(node, part)
    return node


def _value(node: Node | None) -> str | None:
    return node.value if isinstance(node, ScalarNode) else None


def _items(node: Node | None) -> list[Node]:
    return node.value if isinstance(node, SequenceNode) else []


def _signature_data(run: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    signature = run.get("failure_signature")
    if not isinstance(signature, dict):
        raise TemplateRefusal("patch_target_unavailable", "Failure signature is missing or malformed")
    normalized = signature.get("normalized")
    if not isinstance(normalized, dict):
        raise TemplateRefusal("patch_target_unavailable", "Structural signature is missing or malformed")
    attributes = normalized.get("attributes")
    if not isinstance(attributes, dict):
        raise TemplateRefusal("patch_target_unavailable", "Signature attributes are missing or malformed")
    return signature, normalized, attributes


def _signature(run: dict[str, Any], failure_class: str, key: str) -> dict[str, Any]:
    signature, normalized, _ = _signature_data(run)
    if (
        signature.get("class") != failure_class
        or signature.get("key") != key
        or normalized.get("resource_kind") != "Deployment"
        or not isinstance(normalized.get("resource_name"), str)
        or not normalized["resource_name"]
        or not isinstance(normalized.get("container"), str)
        or not normalized["container"]
    ):
        raise TemplateRefusal("patch_target_unavailable", "No exact structural Deployment/container signature")
    return normalized


def _documents(run: dict[str, Any]) -> list[tuple[str, str, Node]]:
    sources = _manifest_sources(run)
    if not sources:
        raise TemplateRefusal("patch_target_unavailable", "Rendered manifests are unavailable")
    documents: list[tuple[str, str, Node]] = []
    for path, content in sources:
        try:
            documents.extend((path, content, doc) for doc in yaml.compose_all(content, Loader=yaml.SafeLoader) if doc)
        except yaml.YAMLError as exc:
            raise TemplateRefusal("patch_target_unavailable", f"Cannot parse rendered manifest: {path}") from exc
    return documents


def _resource(run: dict[str, Any], kind: str, name: str) -> tuple[str, str, Node]:
    matches = [
        (path, content, doc)
        for path, content, doc in _documents(run)
        if _value(_field(doc, "kind")) == kind
        and _value(_at(doc, "metadata", "name")) == name
    ]
    if len(matches) != 1:
        raise TemplateRefusal("patch_target_unavailable", f"Expected one {kind}/{name}, found {len(matches)}")
    return matches[0]


def _container(deployment: Node, name: str) -> Node:
    matches = [
        item for item in _items(_at(deployment, "spec", "template", "spec", "containers"))
        if _value(_field(item, "name")) == name
    ]
    if len(matches) != 1:
        raise TemplateRefusal("patch_target_unavailable", f"Expected one container/{name}, found {len(matches)}")
    return matches[0]


def _reference_count(root: Node, target: Node, active: frozenset[int] = frozenset()) -> int:
    """A YAML alias can make one scalar serve multiple resources; never edit it."""
    if root is target:
        return 1
    if id(root) in active:
        return 0
    active = active | {id(root)}
    if isinstance(root, MappingNode):
        return sum(_reference_count(child, target, active) for pair in root.value for child in pair)
    if isinstance(root, SequenceNode):
        return sum(_reference_count(child, target, active) for child in root.value)
    return 0


def _replace_scalar(path: str, content: str, document: Node, old: Node | None, expected: str, new: str) -> list[dict[str, Any]]:
    if not isinstance(old, ScalarNode) or old.value != expected or expected == new:
        raise TemplateRefusal("patch_target_unavailable", "Observed field no longer matches the signature")
    if _reference_count(document, old) != 1:
        raise TemplateRefusal("patch_target_unavailable", "Target scalar is shared by a YAML alias")
    fixed = content[:old.start_mark.index] + new + content[old.end_mark.index:]
    return [{"path": path, "action": "modify", "content": fixed, "unified_diff_hunk": None}]


def _manifest_dir(run: dict[str, Any]) -> Path | None:
    workspace = run.get("workspace_path")
    if not workspace:
        return None
    root = Path(workspace)
    rel = (run.get("manifests") or {}).get("path") or "deploy/manifests"
    target = root / rel
    if target.is_dir():
        return target
    if target.is_file():
        return target.parent
    return None


def _iter_yaml_files(directory: Path) -> list[Path]:
    return sorted(
        p
        for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in {".yaml", ".yml"}
    )


def _manifest_sources(run: dict[str, Any]) -> list[tuple[str, str]] | None:
    """Return [(relative_path, content)] for the manifests to fix.

    Prefers ``run["rendered_files"]`` — the files the connector actually rendered
    and applied, disclosed by the deploy_revision response (contracts-v1.1.0). This
    lets the deterministic templates operate in the dispatch path without touching
    the customer filesystem.

    The workspace_path fallback below is ONLY for the agent's legacy in-process
    test suite (agent/tests/test_patch.py), which constructs run dicts with
    workspace_path directly and bypasses dispatch/connector entirely. In the
    production dispatch-connector path, workspace_path is NEVER set in
    orchestrator state — dispatch has no filesystem access to customer repos
    by design. Do not treat this fallback as evidence that dispatch sometimes
    reads manifests from disk; it does not.
    """
    rendered = run.get("rendered_files")
    if isinstance(rendered, list) and rendered:
        sources: list[tuple[str, str]] = []
        for item in rendered:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            content = item.get("content")
            if isinstance(path, str) and isinstance(content, str) and path.lower().endswith(
                (".yaml", ".yml")
            ):
                sources.append((path, content))
        return sources or None

    directory = _manifest_dir(run)
    if directory is None:
        return None
    workspace = run.get("workspace_path")
    root = Path(workspace) if workspace else directory
    sources = []
    for path in _iter_yaml_files(directory):
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            rel = path.as_posix()
        sources.append((rel, path.read_text(encoding="utf-8")))
    return sources or None


def fix_probe_port_mismatch(run: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Align readinessProbe.httpGet.port with containerPort in broken manifests."""
    sig, norm, attrs = _signature_data(run)
    name = norm.get("resource_name")
    cp, pp = attrs.get("container_port"), attrs.get("probe_port")
    if (
        norm.get("reason") != "ReadinessProbePortMismatch"
        or not isinstance(cp, int) or not isinstance(pp, int)
        or sig.get("key") != f"probe_port_mismatch:{name}:{cp}!={pp}"
    ):
        raise TemplateRefusal("patch_target_unavailable", "No exact readiness-port signature")
    norm = _signature(run, "probe_misconfiguration", sig["key"])
    path, content, deployment = _resource(run, "Deployment", norm["resource_name"])
    container = _container(deployment, norm["container"])
    ports = _items(_field(container, "ports"))
    if not ports or _value(_field(ports[0], "containerPort")) != str(cp):
        raise TemplateRefusal("patch_target_unavailable", "Container port differs from signature")
    return _replace_scalar(path, content, deployment, _at(container, "readinessProbe", "httpGet", "port"), str(pp), str(cp))


def fix_bad_image(run: dict[str, Any], *, known_good: str = "hashicorp/http-echo:1.0") -> list[dict[str, Any]] | None:
    sig, norm, attrs = _signature_data(run)
    name, image = norm.get("resource_name"), attrs.get("image")
    if (
        not isinstance(image, str) or not image
        or sig.get("key") != f"bad_image:{name}:{image}"
        or not ("does-not-exist" in image or image.endswith(":missing") or "invalid.tag" in image)
    ):
        raise TemplateRefusal("patch_target_unavailable", "No exact structural bad-image signature")
    norm = _signature(run, "bad_image_reference", sig["key"])
    path, content, deployment = _resource(run, "Deployment", norm["resource_name"])
    container = _container(deployment, norm["container"])
    return _replace_scalar(path, content, deployment, _field(container, "image"), image, known_good)


def fix_missing_configmap_key(run: dict[str, Any]) -> list[dict[str, Any]] | None:
    sig, norm, attrs = _signature_data(run)
    cm_name, key = attrs.get("configmap"), attrs.get("key")
    if (
        not isinstance(cm_name, str) or not cm_name
        or not isinstance(key, str) or not key
        or sig.get("key") != f"missing_configmap_key:{cm_name}:{key}"
    ):
        raise TemplateRefusal("patch_target_unavailable", "No exact structural ConfigMap/key signature")
    norm = _signature(run, "invalid_missing_config", sig["key"])
    _, _, deployment = _resource(run, "Deployment", norm["resource_name"])
    container = _container(deployment, norm["container"])
    references = [
        env for env in _items(_field(container, "env"))
        if _value(_at(env, "valueFrom", "configMapKeyRef", "name")) == cm_name
        and _value(_at(env, "valueFrom", "configMapKeyRef", "key")) == key
    ]
    if len(references) != 1:
        raise TemplateRefusal("patch_target_unavailable", "ConfigMap reference is missing or ambiguous")
    _, _, configmap = _resource(run, "ConfigMap", cm_name)
    if _field(_field(configmap, "data"), key) is not None:
        raise TemplateRefusal("patch_target_unavailable", "ConfigMap key is no longer missing")
    raise TemplateRefusal("patch_value_unavailable", f"No evidenced value for ConfigMap/{cm_name} key {key}")


def generate_files_for_diagnosis(run: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, str]:
    """Return (files, summary) for the selected failure class."""
    diagnosis = run.get("diagnosis") or {}
    failure_class = (diagnosis.get("classification") or {}).get("failure_class")
    if not failure_class:
        return None, "No deterministic fix template for failure class"

    from raphael_agent.learning import template_weight_for_run

    weight = template_weight_for_run(run, str(failure_class))
    if weight < 0.4:
        return (
            None,
            f"Learning demoted template for {failure_class} (weight={weight})",
        )

    # The patch-selector model chooses only from bounded template families.
    # Map its names to concrete generators; unknown families fall back to the
    # existing deterministic dispatcher and still require sandbox validation.
    model_template = str(run.get("_model_safe_template") or "")
    if model_template in {"fix_probe_port_mismatch", "adjust_readiness_probe_path", "tune_probe_timeout_seconds"}:
        files = fix_probe_port_mismatch(run)
        return files, "Apply model-selected readiness probe fix"
    if model_template in {"restore_known_good_image", "revert_image_digest"}:
        files = fix_bad_image(run)
        return files, "Apply model-selected known-good image fix"
    if model_template == "restore_configmap_key":
        files = fix_missing_configmap_key(run)
        return files, "Apply model-selected ConfigMap key fix"

    if failure_class == "probe_misconfiguration":
        files = fix_probe_port_mismatch(run)
        return files, "Align readiness probe port with containerPort"
    if failure_class == "bad_image_reference":
        files = fix_bad_image(run)
        return files, "Restore known-good container image tag"
    if failure_class == "invalid_missing_config":
        files = fix_missing_configmap_key(run)
        return files, "Add missing ConfigMap key referenced by the Deployment"
    return None, "No deterministic fix template for failure class"
