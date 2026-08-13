"""Advisory GitHub Check Runs (GH-030–034). Never calls sandbox HTTP.

Gated by ``RAPHAEL_GITHUB_CHECK_RUNS`` (default 0; does not inherit commands
or auto-comments). ``check_run_id`` lives in a sidecar JSON file — never on
``run_record.json``.
"""

from __future__ import annotations

import json
import threading
from typing import Any, Protocol

from raphael_agent.evidence.redaction import redact_text
from raphael_agent.github_commands.config import (
    github_check_advisory_success,
    github_check_runs_enabled,
)
from raphael_agent.github_commands.replies import run_summary_fields
from raphael_agent.patch.policy import path_allowed
from raphael_agent.store import RunStore
from raphael_agent.timeutil import utc_now

CHECK_NAME = "Raphael (advisory)"
SIDECAR_NAME = "github_check_runs.json"
TERMINAL_CHECK_STATUSES = frozenset(
    {
        "success_draft_pr_ready",
        "success_fix_proposed",
        "escalated",
        "failed_closed",
    }
)
ADVISORY_SUCCESS_STATUSES = frozenset(
    {"success_draft_pr_ready", "success_fix_proposed"}
)
_MAX_ANNOTATIONS = 50
_LOCK = threading.Lock()

# Tests may assign a fake publisher. Production stays None.
_CLIENT_OVERRIDE: Any = None


class CheckRunClient(Protocol):
    def create_check_run(self, owner: str, repo: str, **kwargs: Any) -> dict[str, Any]: ...

    def update_check_run(self, owner: str, repo: str, **kwargs: Any) -> dict[str, Any]: ...


def check_conclusion(status: str) -> str:
    """GH-033/034: default ``neutral``. Opt-in ``success`` on happy terminals only.

    Never ``failure`` (must not look like a required merge gate).
    """
    if (
        github_check_advisory_success()
        and status in ADVISORY_SUCCESS_STATUSES
    ):
        return "success"
    return "neutral"


def _sidecar_path(store: RunStore):
    return store.root / SIDECAR_NAME


def _load_sidecar(store: RunStore) -> dict[str, Any]:
    path = _sidecar_path(store)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _row(store: RunStore, run_id: str) -> dict[str, Any] | None:
    row = _load_sidecar(store).get(run_id)
    return row if isinstance(row, dict) else None


def _save_row(store: RunStore, run_id: str, row: dict[str, Any]) -> None:
    path = _sidecar_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        data = _load_sidecar(store)
        data[run_id] = row
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _repo_and_sha(run: dict[str, Any]) -> tuple[str, str, str] | None:
    repo = run.get("repository") or {}
    owner = str(repo.get("owner") or "")
    name = str(repo.get("name") or "")
    sha = str(run.get("commit_sha") or "")
    if not owner or not name or not sha:
        return None
    return owner, name, sha


def _client(explicit: CheckRunClient | None) -> CheckRunClient | None:
    if explicit is not None:
        return explicit
    if _CLIENT_OVERRIDE is not None:
        return _CLIENT_OVERRIDE
    from raphael_agent.publish.config import github_token

    if not github_token():
        return None
    try:
        from raphael_agent.publish.github_client import GitHubPublisher

        return GitHubPublisher()
    except Exception:  # noqa: BLE001
        return None


def _active_patch(run: dict[str, Any]) -> dict[str, Any] | None:
    active = run.get("active_patch_id")
    for patch in run.get("candidate_patches") or []:
        if patch.get("patch_id") == active:
            return patch
    patches = list(run.get("candidate_patches") or [])
    return patches[-1] if patches else None


def _looks_like_secret_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    name = lowered.rsplit("/", 1)[-1]
    if name in {".env", ".env.local", ".env.production"}:
        return True
    if "secret" in lowered and lowered.endswith((".env", ".pem", ".key")):
        return True
    return False


def annotations_for_run(run: dict[str, Any]) -> list[dict[str, Any]]:
    """GH-032: notice-level annotations on allowlisted patch paths only."""
    patch = _active_patch(run) or {}
    annotations: list[dict[str, Any]] = []
    for file_entry in patch.get("files") or []:
        if len(annotations) >= _MAX_ANNOTATIONS:
            break
        path = str(file_entry.get("path") or "").replace("\\", "/").lstrip("/")
        if not path or not path_allowed(path) or _looks_like_secret_path(path):
            continue
        content = file_entry.get("content")
        if isinstance(content, str) and content:
            _, secret_notes = redact_text(content)
            if secret_notes:
                continue
        message = (
            f"Proposed change on allowlisted path `{path}`. "
            "This Check is advisory and does not replace human review. "
            "Raphael never merges."
        )
        redacted, _ = redact_text(message)
        annotations.append(
            {
                "path": path,
                "start_line": 1,
                "end_line": 1,
                "annotation_level": "notice",
                "message": redacted[:65535],
                "title": CHECK_NAME,
            }
        )
    return annotations


def _validation_markdown(run: dict[str, Any]) -> str:
    from raphael_agent.publish.pr_body import _validation_rows

    return "\n".join(_validation_rows(run))


def render_check_output(run: dict[str, Any], *, in_progress: bool = False) -> dict[str, Any]:
    fields = run_summary_fields(run)
    status = fields["status"]
    title = f"{CHECK_NAME} — {status}"[:255]
    summary = (
        f"**{CHECK_NAME}.** This Check is advisory and does not replace human review. "
        "It is never a required merge gate. Raphael never merges.\n\n"
        f"- **run_id:** `{fields['run_id']}`\n"
        f"- **Status:** {status}\n"
        f"- **Class:** {fields['failure_class']} (confidence {fields['confidence']})\n"
        f"- **Sandbox result:** `{fields['result_id']}`\n"
        f"- **Delivery:** {fields['delivery']}\n"
        f"- **Mode:** partner={fields['partner_mode']} publish={fields['publish_mode']}\n"
    )
    if not in_progress:
        summary += f"- **Reason:** {fields['terminal_reason']}\n"
    summary, _ = redact_text(summary)

    text_parts = [
        summary,
        "",
        "### Validation matrix",
        _validation_markdown(run),
        "",
        "### Next step",
        fields["next_step"],
        "",
        "There is no Merge action on this Check.",
    ]
    text, _ = redact_text("\n".join(text_parts))
    output: dict[str, Any] = {
        "title": title,
        "summary": summary[:65535],
        "text": text[:65535],
    }
    if not in_progress:
        anns = annotations_for_run(run)
        if anns:
            output["annotations"] = anns
    return output


def maybe_start_check_run(
    run: dict[str, Any],
    *,
    store: RunStore | None = None,
    client: CheckRunClient | None = None,
) -> dict[str, Any]:
    """Create or refresh an in-progress advisory Check. Never raises."""
    try:
        return _start(run, store=store, client=client)
    except Exception as exc:  # noqa: BLE001
        return {"decision": "skipped", "reason": f"error:{type(exc).__name__}"}


def maybe_complete_check_run(
    run: dict[str, Any],
    *,
    store: RunStore | None = None,
    client: CheckRunClient | None = None,
) -> dict[str, Any]:
    """PATCH (or create) a completed advisory Check. Never raises. Never ``failure``."""
    try:
        return _complete(run, store=store, client=client)
    except Exception as exc:  # noqa: BLE001
        return {"decision": "skipped", "reason": f"error:{type(exc).__name__}"}


def _start(
    run: dict[str, Any],
    *,
    store: RunStore | None,
    client: CheckRunClient | None,
) -> dict[str, Any]:
    if not github_check_runs_enabled():
        return {"decision": "skipped", "reason": "check_runs_disabled"}
    run_id = str(run.get("run_id") or "")
    target = _repo_and_sha(run)
    if not run_id or target is None:
        return {"decision": "skipped", "reason": "missing_repo_or_sha"}
    owner, repo, sha = target
    store = store or RunStore()
    existing = _row(store, run_id)
    if existing and existing.get("check_run_id"):
        return {
            "decision": "idempotent",
            "run_id": run_id,
            "check_run_id": existing.get("check_run_id"),
            "phase": existing.get("phase"),
        }

    ops = _client(client)
    if ops is None:
        return {"decision": "skipped", "reason": "no_github_client", "run_id": run_id}

    output = render_check_output({**run, "status": run.get("status") or "running"}, in_progress=True)
    created = ops.create_check_run(
        owner,
        repo,
        head_sha=sha,
        name=CHECK_NAME,
        status="in_progress",
        output=output,
        started_at=utc_now(),
        external_id=run_id,
    )
    check_id = (created or {}).get("id")
    _save_row(
        store,
        run_id,
        {
            "check_run_id": check_id,
            "head_sha": sha,
            "phase": "in_progress",
            "at": utc_now(),
        },
    )
    return {
        "decision": "created",
        "run_id": run_id,
        "check_run_id": check_id,
        "output": output,
    }


def _complete(
    run: dict[str, Any],
    *,
    store: RunStore | None,
    client: CheckRunClient | None,
) -> dict[str, Any]:
    if not github_check_runs_enabled():
        return {"decision": "skipped", "reason": "check_runs_disabled"}
    status = str(run.get("status") or "")
    if status not in TERMINAL_CHECK_STATUSES:
        return {"decision": "skipped", "reason": f"status={status}"}
    run_id = str(run.get("run_id") or "")
    target = _repo_and_sha(run)
    if not run_id or target is None:
        return {"decision": "skipped", "reason": "missing_repo_or_sha"}
    owner, repo, sha = target
    store = store or RunStore()
    conclusion = check_conclusion(status)
    if conclusion not in {"neutral", "success"}:
        conclusion = "neutral"
    output = render_check_output(run, in_progress=False)
    ops = _client(client)
    if ops is None:
        return {
            "decision": "skipped",
            "reason": "no_github_client",
            "run_id": run_id,
            "conclusion": conclusion,
            "output": output,
        }

    existing = _row(store, run_id)
    check_id = existing.get("check_run_id") if existing else None
    completed_at = utc_now()
    if check_id is not None:
        ops.update_check_run(
            owner,
            repo,
            check_run_id=int(check_id),
            name=CHECK_NAME,
            status="completed",
            conclusion=conclusion,
            output=output,
            completed_at=completed_at,
        )
        decision = "updated"
    else:
        created = ops.create_check_run(
            owner,
            repo,
            head_sha=sha,
            name=CHECK_NAME,
            status="completed",
            conclusion=conclusion,
            output=output,
            completed_at=completed_at,
            external_id=run_id,
        )
        check_id = (created or {}).get("id")
        decision = "created"
    _save_row(
        store,
        run_id,
        {
            "check_run_id": check_id,
            "head_sha": sha,
            "phase": "completed",
            "conclusion": conclusion,
            "status": status,
            "at": completed_at,
        },
    )
    return {
        "decision": decision,
        "run_id": run_id,
        "check_run_id": check_id,
        "conclusion": conclusion,
        "output": output,
    }
