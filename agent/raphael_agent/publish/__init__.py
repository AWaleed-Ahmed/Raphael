"""Publish draft GitHub PRs from a frozen sandbox result_id (Phase 3)."""

from __future__ import annotations

from typing import Any

from raphael_agent.publish.branch import branch_name_for_run, pr_title_for_run
from raphael_agent.publish.config import (
    base_branch,
    effective_publish_mode,
    github_token,
    partner_mode,
)
from raphael_agent.publish.github_client import GitHubApiError, GitHubPublisher
from raphael_agent.publish.pr_body import build_pr_body
from raphael_agent.schema_util import validate_agent

__all__ = [
    "publish",
    "stub_publish",
    "build_pr_body",
    "branch_name_for_run",
    "pr_title_for_run",
]


def _active_patch_files(run: dict[str, Any]) -> list[dict[str, Any]]:
    active = run.get("active_patch_id")
    patches = run.get("candidate_patches") or []
    patch = next((p for p in patches if p.get("patch_id") == active), None)
    if patch is None and patches:
        patch = patches[-1]
    if not patch:
        return []
    if patch.get("policy_status") == "rejected":
        return []
    files: list[dict[str, Any]] = []
    for entry in patch.get("files") or []:
        if entry.get("action") == "delete":
            continue
        content = entry.get("content")
        path = entry.get("path")
        if not path or not isinstance(content, str):
            continue
        # Skip deploy-hint marker files that are not real repo content.
        if str(path).endswith(".raphael-use-fixed-tree") or str(path).endswith(
            ".raphael-empty-patch"
        ):
            continue
        files.append({"path": path, "content": content, "action": entry.get("action")})
    return files


def _dry_run_url(owner: str, repo: str, *, base: str, branch: str) -> str:
    return (
        f"https://github.com/{owner}/{repo}/compare/{base}...{branch}"
        f"?expand=1&raphael_dry_run=1"
    )


def _fail(
    *,
    error: str,
    message: str,
    result_id: str | None,
    branch: str,
    base: str,
    mode: str,
) -> dict[str, Any]:
    out = {
        "ok": False,
        "mode": mode,
        "draft": True,
        "result_id": result_id or "",
        "branch": branch,
        "base_branch": base,
        "pull_request_url": None,
        "pull_request_number": None,
        "title": "",
        "dry_run": mode == "dry_run",
        "idempotent_replay": False,
        "error": error,
        "message": message,
        "html_compare_url": None,
        "committed_files": [],
    }
    # result_id required in schema — use placeholder when missing for validation of error path? 
    # Schema requires minLength 1. Use "missing" sentinel for fail-closed paths.
    if not out["result_id"]:
        out["result_id"] = "missing"
    return out


def publish(
    run: dict[str, Any],
    *,
    github: GitHubPublisher | None = None,
) -> dict[str, Any]:
    """Open a draft PR (or dry-run) gated on ``result_id``. Never merges."""
    mode = effective_publish_mode(run)
    partner = partner_mode()
    base = base_branch()
    branch = branch_name_for_run(run)
    title = pr_title_for_run(run)
    result_id = run.get("result_id")

    # Idempotency: reuse prior publish on this run.
    existing = run.get("publish") or {}
    if run.get("pull_request_url") and existing.get("ok"):
        replay = dict(existing)
        replay["idempotent_replay"] = True
        replay["message"] = "Reused existing pull_request_url (idempotent)"
        validate_agent("publish_result.json", replay)
        return replay

    if run.get("status") in {"escalated", "failed_closed"}:
        return _fail(
            error="run_not_publishable",
            message=f"Refuse to publish when status={run.get('status')}",
            result_id=result_id,
            branch=branch,
            base=base,
            mode=mode,
        )

    if not result_id:
        return _fail(
            error="result_id_required",
            message="Publish refuses to proceed without a frozen sandbox result_id",
            result_id=result_id,
            branch=branch,
            base=base,
            mode=mode,
        )

    # Require at least one passing validation when recorded.
    validations = run.get("validation_results") or []
    record = run.get("validated_fix_record") or {}
    if record.get("validation"):
        validations = list(validations) + [record["validation"]]
    if validations and not any(v.get("passed") and not v.get("fail_closed") for v in validations):
        return _fail(
            error="validation_not_passed",
            message="Publish fail-closed: no passing validation_results for this run",
            result_id=result_id,
            branch=branch,
            base=base,
            mode=mode,
        )

    repo = run.get("repository") or {}
    owner = repo.get("owner")
    name = repo.get("name")
    if not owner or not name:
        return _fail(
            error="repository_required",
            message="repository.owner/name required to publish",
            result_id=result_id,
            branch=branch,
            base=base,
            mode=mode,
        )

    files = _active_patch_files(run)
    body = build_pr_body(run)

    if mode == "dry_run":
        url = _dry_run_url(owner, name, base=base, branch=branch)
        reason = (
            "partner diagnosis_only"
            if partner == "diagnosis_only"
            else (
                "partner dry_run / failure class not allowlisted for live"
                if partner == "allowlist"
                else "RAPHAEL_PARTNER_MODE=dry_run or RAPHAEL_PUBLISH_MODE!=live"
            )
        )
        result = {
            "ok": True,
            "mode": "dry_run",
            "draft": True,
            "result_id": result_id,
            "branch": branch,
            "base_branch": base,
            "pull_request_url": url,
            "pull_request_number": None,
            "title": title,
            "dry_run": True,
            "idempotent_replay": False,
            "error": None,
            "message": (
                f"Dry-run draft PR prepared for result_id={result_id}; "
                f"no GitHub mutation ({reason})"
            ),
            "html_compare_url": url,
            "committed_files": [f["path"] for f in files],
        }
        validate_agent("publish_result.json", result)
        _maybe_record_publish_feedback(run, result)
        return result

    # live mode
    if not github_token() and github is None:
        return _fail(
            error="github_token_required",
            message="Live publish requires RAPHAEL_GITHUB_TOKEN (or GITHUB_TOKEN)",
            result_id=result_id,
            branch=branch,
            base=base,
            mode=mode,
        )
    if not files:
        return _fail(
            error="no_patch_files",
            message="Live publish requires constrained patch file contents",
            result_id=result_id,
            branch=branch,
            base=base,
            mode=mode,
        )

    client = github or GitHubPublisher()
    try:
        head_sha = run.get("commit_sha") or client.get_ref_sha(owner, name, base)
        # Prefer creating branch from base tip so PR is mergeable; fall back to commit_sha.
        try:
            from_sha = client.get_ref_sha(owner, name, base)
        except GitHubApiError:
            from_sha = head_sha
        client.ensure_branch(owner, name, branch=branch, from_sha=from_sha)
        existing_pr = client.find_open_pr(owner, name, head_branch=branch)
        committed: list[str] = []
        if existing_pr is None:
            for entry in files:
                client.put_file(
                    owner,
                    name,
                    path=entry["path"],
                    content=entry["content"],
                    branch=branch,
                    message=f"raphael: {title} ({result_id})",
                )
                committed.append(entry["path"])
        pr = existing_pr or client.create_draft_pr(
            owner,
            name,
            title=title,
            body=body,
            head=branch,
            base=base,
        )
        url = pr.get("html_url")
        number = pr.get("number")
        result = {
            "ok": True,
            "mode": "live",
            "draft": True,
            "result_id": result_id,
            "branch": branch,
            "base_branch": base,
            "pull_request_url": url,
            "pull_request_number": number,
            "title": title,
            "dry_run": False,
            "idempotent_replay": existing_pr is not None,
            "error": None,
            "message": (
                f"Reused open draft PR #{number} for result_id={result_id}"
                if existing_pr is not None
                else f"Opened draft PR #{number} for result_id={result_id}"
            ),
            "html_compare_url": None,
            "committed_files": committed,
        }
        validate_agent("publish_result.json", result)
        _maybe_record_publish_feedback(run, result)
        return result
    except GitHubApiError as exc:
        return _fail(
            error="github_api_error",
            message=f"GitHub API error HTTP {exc.status_code}: {exc}",
            result_id=result_id,
            branch=branch,
            base=base,
            mode=mode,
        )
    except Exception as exc:  # noqa: BLE001 — fail closed
        return _fail(
            error="publish_failed",
            message=str(exc),
            result_id=result_id,
            branch=branch,
            base=base,
            mode=mode,
        )


def _maybe_record_publish_feedback(run: dict[str, Any], result: dict[str, Any]) -> None:
    from raphael_agent.feedback import (
        default_feedback_recorder,
        feedback_from_run,
        feedback_on_publish_enabled,
    )

    if not feedback_on_publish_enabled() or not result.get("ok"):
        return
    outcome = "dry_run_prepared" if result.get("dry_run") else "draft_opened"
    merged = {**run, "publish": result, "pull_request_url": result.get("pull_request_url")}
    event = feedback_from_run(merged, outcome=outcome, source="publish")
    try:
        default_feedback_recorder().record(event)
    except Exception:  # noqa: BLE001 — feedback must not break publish
        return


def stub_publish(run: dict[str, Any]) -> dict[str, Any]:
    """Back-compat alias — delegates to publish()."""
    return publish(run)
