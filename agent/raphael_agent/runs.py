"""I0 run list / create / actions (served by http_api).

Kept as ``runs.py`` (not a package directory) so Git does not confuse it with
RunStore JSON under ``.raphael-agent-data/runs/``.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from jsonschema import ValidationError

from raphael_agent.feedback import default_feedback_recorder, feedback_from_run
from raphael_agent.graph.state import append_audit, initial_run_state
from raphael_agent.ingest.normalize import normalize_failed_run_event
from raphael_agent.ingest.policy import IngestPolicyConfig
from raphael_agent.ingest.service import accept_normalized_event
from raphael_agent.schema_util import for_run_record_validation, validate_agent
from raphael_agent.store import RunStore
from raphael_agent.telemetry_supabase import record_run_outcome
from raphael_agent.timeutil import utc_now

IN_FLIGHT = frozenset({"pending", "running"})
MANUAL_KINDS = frozenset({"manual_ui", "manual_ide", "manual_github", "manual", "fixture"})
_LOG_LOCK = threading.Lock()


class RunApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def _bool_env(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def should_run_manual_graph() -> bool:
    """Default on; set RAPHAEL_MANUAL_RUN_GRAPH=0 to persist pending only."""
    raw = os.environ.get("RAPHAEL_MANUAL_RUN_GRAPH", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _actions_path(store: RunStore) -> Path:
    return store.root / "interface_actions.jsonl"


def _payload_fingerprint(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _read_action_log(store: RunStore) -> list[dict[str, Any]]:
    path = _actions_path(store)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _find_action(store: RunStore, action_id: str) -> dict[str, Any] | None:
    for row in reversed(_read_action_log(store)):
        if row.get("action_id") == action_id:
            return row
    return None


def _append_action(store: RunStore, record: dict[str, Any]) -> None:
    path = _actions_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")


def _replay_or_conflict(
    store: RunStore, action_id: str, fingerprint: str
) -> dict[str, Any] | None:
    existing = _find_action(store, action_id)
    if existing is None:
        return None
    if existing.get("payload_fingerprint") != fingerprint:
        raise RunApiError(
            "conflict_idempotency",
            "action_id already used with a different payload",
            status=409,
        )
    result = dict(existing.get("result") or {})
    result["idempotent_replay"] = True
    return result


def _record_result(
    store: RunStore,
    *,
    action_id: str,
    fingerprint: str,
    kind: str,
    result: dict[str, Any],
) -> None:
    _append_action(
        store,
        {
            "action_id": action_id,
            "kind": kind,
            "payload_fingerprint": fingerprint,
            "recorded_at": utc_now(),
            "result": result,
        },
    )


def _repo_owner_name(run: dict[str, Any]) -> tuple[str, str]:
    repo = run.get("repository") or {}
    return str(repo.get("owner") or ""), str(repo.get("name") or "")


def _failure_class(run: dict[str, Any]) -> str | None:
    classification = (run.get("diagnosis") or {}).get("classification") or {}
    value = classification.get("failure_class")
    return str(value) if value else None


def _summary_row(run: dict[str, Any]) -> dict[str, Any]:
    owner, name = _repo_owner_name(run)
    trigger = run.get("trigger") or {}
    row: dict[str, Any] = {
        "run_id": run["run_id"],
        "status": run["status"],
        "repository": {"owner": owner, "name": name},
        "commit_sha": run["commit_sha"],
        "created_at": run.get("created_at") or utc_now(),
        "updated_at": run.get("updated_at") or run.get("created_at") or utc_now(),
    }
    optional = {
        "terminal_reason": run.get("terminal_reason"),
        "failure_class": _failure_class(run),
        "issue_number": run.get("issue_number"),
        "pull_request_number": run.get("pull_request_number"),
        "pull_request_url": run.get("pull_request_url"),
        "parent_run_id": run.get("parent_run_id"),
        "trigger_kind": trigger.get("kind"),
    }
    for key, value in optional.items():
        if value is not None:
            row[key] = value
    return row


def list_runs(
    store: RunStore,
    *,
    owner: str | None = None,
    repo: str | None = None,
    status: str | None = None,
    issue_number: int | None = None,
    pull_request_number: int | None = None,
    limit: int = 20,
    cursor: str | None = None,
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise RunApiError("invalid_request", "limit must be between 1 and 100")
    rows = list(store.iter_runs())
    rows.sort(key=lambda r: r.get("updated_at") or r.get("created_at") or "", reverse=True)
    filtered: list[dict[str, Any]] = []
    for run in rows:
        run_owner, run_name = _repo_owner_name(run)
        if owner and run_owner != owner:
            continue
        if repo and run_name != repo:
            continue
        if status and run.get("status") != status:
            continue
        if issue_number is not None and run.get("issue_number") != issue_number:
            continue
        if pull_request_number is not None and run.get(
            "pull_request_number"
        ) != pull_request_number:
            continue
        filtered.append(run)

    if cursor:
        skip = True
        trimmed: list[dict[str, Any]] = []
        for run in filtered:
            if skip:
                if run.get("run_id") == cursor:
                    skip = False
                continue
            trimmed.append(run)
        filtered = trimmed

    page = filtered[:limit]
    next_cursor = page[-1]["run_id"] if len(filtered) > limit else None
    payload: dict[str, Any] = {
        "runs": [_summary_row(r) for r in page],
        "limit": limit,
    }
    if next_cursor is not None:
        payload["next_cursor"] = next_cursor
    validate_agent("run_list_response.json", payload)
    return payload


def find_latest_run_for_github_number(
    store: RunStore,
    *,
    owner: str,
    repo: str,
    number: int,
) -> dict[str, Any] | None:
    """Latest run whose issue_number or pull_request_number matches ``number``."""
    matches: list[dict[str, Any]] = []
    for run in store.iter_runs():
        run_owner, run_name = _repo_owner_name(run)
        if run_owner != owner or run_name != repo:
            continue
        if run.get("issue_number") == number or run.get("pull_request_number") == number:
            matches.append(run)
    if not matches:
        return None
    matches.sort(key=lambda r: r.get("updated_at") or r.get("created_at") or "")
    return matches[-1]


def delivery_patch_from_run(run: dict[str, Any]) -> str | None:
    patches = list(run.get("candidate_patches") or [])
    active_id = run.get("active_patch_id")
    selected: dict[str, Any] | None = None
    if active_id:
        selected = next((p for p in patches if p.get("patch_id") == active_id), None)
    if selected is None and patches:
        selected = patches[-1]
    if selected:
        diff = selected.get("unified_diff")
        if isinstance(diff, str) and diff.strip():
            return diff
        hunks = [
            str(f.get("unified_diff_hunk"))
            for f in (selected.get("files") or [])
            if f.get("unified_diff_hunk")
        ]
        if hunks:
            return "\n".join(hunks)
    snippet = (run.get("publish") or {}).get("fix_snippet")
    if isinstance(snippet, str) and snippet.strip():
        return snippet
    return None


def _maybe_run_graph(run: dict[str, Any], store: RunStore) -> dict[str, Any]:
    if not should_run_manual_graph():
        store.save_run(dict(run))
        return run
    from raphael_agent.graph import run_stub_graph

    final = run_stub_graph(run)
    store.save_run(dict(final))
    return dict(final)


def create_run(body: dict[str, Any], *, store: RunStore) -> dict[str, Any]:
    try:
        validate_agent("run_create_request.json", body)
    except ValidationError as exc:
        raise RunApiError("invalid_request", str(exc.message)) from exc

    action_id = str(body["action_id"])
    fingerprint = _payload_fingerprint(body)
    replay = _replay_or_conflict(store, action_id, fingerprint)
    if replay is not None:
        return replay

    sandbox_mode = body.get("sandbox_mode") or os.environ.get(
        "RAPHAEL_AGENT_SANDBOX_MODE", "skipped"
    )
    event: dict[str, Any] = {
        "run_id": f"run-{uuid.uuid4().hex[:12]}",
        "trigger_kind": body["trigger_kind"],
        "event_id": action_id,
        "repository": body["repository"],
        "commit_sha": body["commit_sha"],
        "raw_ref": f"interface:create:{action_id}",
    }
    for key in (
        "tenant_id",
        "target_environment",
        "workspace_path",
        "manifests",
        "issue_number",
        "pull_request_number",
        "notes",
        "actor",
        "delivery_mode",
        "issue_labels",
        "issue_title",
        "issue_body",
        "failure_class_hint",
        "diagnosis_only",
    ):
        if body.get(key) is not None:
            event[key] = body[key]

    seed = normalize_failed_run_event(event)
    try:
        decision, run = accept_normalized_event(
            seed,
            store=store,
            policy=IngestPolicyConfig.from_env(),
            raw_payload=body,
            sandbox_mode=str(sandbox_mode),
        )
    except Exception as exc:  # noqa: BLE001
        raise RunApiError("invalid_request", str(exc)) from exc

    if run is None:
        raise RunApiError(
            "conflict_state",
            decision.get("reason") or "ingest rejected create",
            status=409,
        )

    run = _maybe_run_graph(run, store)
    result = {
        "run_id": run["run_id"],
        "status": run["status"],
        "action_id": action_id,
        "idempotent_replay": False,
        "message": "run created",
    }
    validate_agent("run_create_response.json", result)
    _record_result(
        store, action_id=action_id, fingerprint=fingerprint, kind="create", result=result
    )
    return result


def _seed_from_parent(parent: dict[str, Any], *, sandbox_mode: str) -> dict[str, Any]:
    trigger = parent.get("trigger") or {}
    kind = trigger.get("kind") if trigger.get("kind") in MANUAL_KINDS else "manual_ui"
    event: dict[str, Any] = {
        "run_id": f"run-{uuid.uuid4().hex[:12]}",
        "trigger_kind": kind,
        "event_id": f"retry:{parent.get('run_id')}",
        "repository": parent.get("repository") or {},
        "commit_sha": parent.get("commit_sha"),
        "tenant_id": parent.get("tenant_id"),
        "parent_run_id": parent.get("run_id"),
        "raw_ref": f"interface:retry:{parent.get('run_id')}",
    }
    for key in (
        "target_environment",
        "workspace_path",
        "manifests",
        "issue_number",
        "pull_request_number",
        "affected_resources",
        "delivery_mode",
        "issue_labels",
        "issue_title",
        "issue_body",
        "failure_class_hint",
        "fix_rules",
    ):
        if parent.get(key) is not None:
            event[key] = parent[key]
    seed = normalize_failed_run_event(event)
    if parent.get("failure_fingerprint"):
        seed["failure_fingerprint"] = parent["failure_fingerprint"]
    if parent.get("correlation"):
        seed["correlation"] = dict(parent["correlation"])
    seed["parent_run_id"] = parent["run_id"]
    run = initial_run_state(seed, sandbox_mode=sandbox_mode)
    run["failure_fingerprint"] = seed.get("failure_fingerprint") or parent.get(
        "failure_fingerprint"
    )
    run["parent_run_id"] = parent["run_id"]
    run["audit_events"] = append_audit(
        run, "interface", "retry", f"parent={parent.get('run_id')}"
    )
    return run


def apply_run_action(
    run_id: str, body: dict[str, Any], *, store: RunStore
) -> dict[str, Any]:
    try:
        validate_agent("run_action_request.json", body)
    except ValidationError as exc:
        raise RunApiError("invalid_request", str(exc.message)) from exc

    action_id = str(body["action_id"])
    verb = str(body["verb"])
    fingerprint = _payload_fingerprint({"run_id": run_id, **body})
    replay = _replay_or_conflict(store, action_id, fingerprint)
    if replay is not None:
        return replay

    run = store.get_run(run_id)
    if run is None:
        raise RunApiError("not_found", f"run not found: {run_id}", status=404)

    status = run.get("status")
    notes = body.get("notes")
    actor = body.get("actor")
    result_run = run
    feedback_event_id: str | None = None
    message = ""
    terminal_reason = run.get("terminal_reason")

    if verb == "feedback":
        event = feedback_from_run(
            run,
            outcome=str(body["outcome"]),
            source="http",
            notes=notes,
            actor=actor,
        )
        recorded = default_feedback_recorder().record(event)
        feedback_event_id = recorded["event_id"]
        run["audit_events"] = append_audit(
            run, "interface", "feedback", str(body["outcome"])
        )
        run["updated_at"] = utc_now()
        store.save_run(run)
        result_run = run
        message = "feedback recorded"

    elif verb == "escalate":
        if status in IN_FLIGHT:
            run["status"] = "escalated"
            run["terminal_reason"] = "human_requested"
            terminal_reason = "human_requested"
            message = "run escalated (human_requested)"
        else:
            message = "escalate on terminal run is notes/audit only"
            terminal_reason = run.get("terminal_reason")
        run["audit_events"] = append_audit(
            run, "interface", "escalate", notes or "human_requested"
        )
        if notes:
            event = feedback_from_run(
                run,
                outcome="other",
                source="http",
                notes=notes,
                actor=actor,
            )
            recorded = default_feedback_recorder().record(event)
            feedback_event_id = recorded["event_id"]
        run["updated_at"] = utc_now()
        store.save_run(run)
        if status in IN_FLIGHT:
            record_run_outcome(run)
        result_run = run
        if status in IN_FLIGHT:
            try:

                from raphael_agent.github_commands.check_runs import maybe_complete_check_run

                maybe_complete_check_run(run, store=store)
            except Exception:  # noqa: BLE001
                pass

    elif verb == "cancel":
        if status not in IN_FLIGHT:
            raise RunApiError(
                "conflict_state",
                f"cannot cancel run in status {status}",
                status=409,
            )
        run["status"] = "cancelled"
        run["terminal_reason"] = "cancelled"
        terminal_reason = "cancelled"
        run["audit_events"] = append_audit(run, "interface", "cancel", notes)
        run["updated_at"] = utc_now()
        store.save_run(run)
        record_run_outcome(run)
        result_run = run
        message = "run cancelled"

    elif verb == "retry":
        if status in IN_FLIGHT:
            raise RunApiError(
                "conflict_state",
                f"retry not needed; run {run_id} is still {status}",
                status=409,
            )
        sandbox_mode = body.get("sandbox_mode") or run.get("sandbox_mode") or "skipped"
        child = _seed_from_parent(run, sandbox_mode=str(sandbox_mode))
        parent_id = run["run_id"]
        if should_run_manual_graph():
            from raphael_agent.graph import run_stub_graph

            child = dict(run_stub_graph(child))
        child["parent_run_id"] = parent_id
        try:
            validate_agent("run_record.json", for_run_record_validation(child))
        except ValidationError:
            pass
        store.save_run(dict(child))
        result_run = child
        message = f"retry created {child.get('run_id')}"
        terminal_reason = child.get("terminal_reason")
        try:
            from raphael_agent.github_commands.check_runs import (
                maybe_complete_check_run,
                maybe_start_check_run,
            )

            maybe_start_check_run(child, store=store)
            maybe_complete_check_run(child, store=store)
        except Exception:  # noqa: BLE001
            pass

    else:
        raise RunApiError("invalid_request", f"unsupported verb: {verb}")

    result: dict[str, Any] = {
        "verb": verb,
        "action_id": action_id,
        "source_run_id": run_id,
        "result_run_id": result_run.get("run_id"),
        "status": result_run.get("status"),
        "idempotent_replay": False,
        "message": message,
    }
    if feedback_event_id:
        result["feedback_event_id"] = feedback_event_id
    if terminal_reason:
        result["terminal_reason"] = terminal_reason
    validate_agent("run_action_response.json", result)
    _record_result(
        store, action_id=action_id, fingerprint=fingerprint, kind="action", result=result
    )
    return result
