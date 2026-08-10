"""Structured draft PR body (PRD §13.2)."""

from __future__ import annotations

from typing import Any


def _active_patch(run: dict[str, Any]) -> dict[str, Any] | None:
    active = run.get("active_patch_id")
    for patch in run.get("candidate_patches") or []:
        if patch.get("patch_id") == active:
            return patch
    patches = run.get("candidate_patches") or []
    return patches[-1] if patches else None


def _validation_rows(run: dict[str, Any]) -> list[str]:
    rows = ["| Check | Kind | Status | Duration (ms) |", "|---|---|---|---|"]
    results = list(run.get("validation_results") or [])
    record = run.get("validated_fix_record") or {}
    if record.get("validation") and not results:
        results = [record["validation"]]
    for result in results[-1:]:
        for check in result.get("checks") or []:
            rows.append(
                "| {name} | {kind} | {status} | {dur} |".format(
                    name=check.get("name", ""),
                    kind=check.get("kind", ""),
                    status=check.get("status", ""),
                    dur=check.get("duration_ms", ""),
                )
            )
    if len(rows) == 2:
        rows.append("| _(none recorded)_ |  |  |  |")
    return rows


def build_pr_body(run: dict[str, Any]) -> str:
    """Markdown body with required audit sections. Evidence must already be redacted."""
    repo = run.get("repository") or {}
    owner = repo.get("owner", "")
    name = repo.get("name", "")
    sha = run.get("commit_sha", "")
    trigger = run.get("trigger") or {}
    diagnosis = run.get("diagnosis") or {}
    classification = diagnosis.get("classification") or {}
    selected_id = diagnosis.get("selected_hypothesis_id")
    hypothesis = next(
        (h for h in (diagnosis.get("hypotheses") or []) if h.get("hypothesis_id") == selected_id),
        (diagnosis.get("hypotheses") or [{}])[0] if diagnosis.get("hypotheses") else {},
    )
    patch = _active_patch(run) or {}
    rationale = patch.get("rationale") or {}
    repro = run.get("reproduction_result") or {}
    record = run.get("validated_fix_record") or {}
    before_sig = (
        (record.get("before_signature") or {}).get("key")
        or repro.get("signature_key")
        or (run.get("failure_signature") or {}).get("key")
    )
    after_sig = (record.get("after_signature") or {}).get("key")
    fidelity = record.get("fidelity") or {}
    result_id = run.get("result_id") or record.get("result_id") or ""
    sandbox_id = run.get("sandbox_id") or record.get("sandbox_id")

    evidence_lines: list[str] = []
    for item in (run.get("evidence") or [])[:8]:
        eid = item.get("evidence_id", "")
        excerpt = (item.get("content_excerpt") or item.get("summary") or "").strip()
        if len(excerpt) > 240:
            excerpt = excerpt[:237] + "..."
        evidence_lines.append(f"- `{eid}` ({item.get('kind')}): {excerpt}")
    if not evidence_lines:
        evidence_lines = ["- _(no evidence items)_"]

    files = patch.get("files") or []
    change_lines = [
        f"- `{f.get('path')}` ({f.get('action')})" for f in files
    ] or ["- _(no file list)_"]

    fidelity_gaps = fidelity.get("material_gaps") or []
    fidelity_text = (
        ", ".join(str(g) for g in fidelity_gaps)
        if fidelity_gaps
        else "See checklist on frozen validated_fix_record"
    )

    sections = [
        "## Incident summary",
        (
            f"Deployment failure for `{owner}/{name}` at commit `{sha}` "
            f"(trigger `{trigger.get('kind')}`, event `{trigger.get('event_id')}`, "
            f"environment `{run.get('target_environment')}`)."
        ),
        f"- **Raphael run_id:** `{run.get('run_id')}`",
        f"- **Tenant:** `{run.get('tenant_id')}`",
        "",
        "## Root cause",
        f"- **Classification:** `{classification.get('category')}` / `{classification.get('failure_class')}`",
        f"- **Selected hypothesis:** {hypothesis.get('statement') or '_(none)_'}",
        f"- **Confidence:** {diagnosis.get('confidence')}",
        f"- **Analyzer:** `{(diagnosis.get('analyzer') or {}).get('name')}` "
        f"({(diagnosis.get('analyzer') or {}).get('mode')})",
        "",
        "## Evidence",
        *evidence_lines,
        f"- **Before signature key:** `{before_sig}`",
        f"- **After signature key:** `{after_sig}`",
        "",
        "## Change",
        rationale.get("summary") or "Constrained patch from diagnosis fix template.",
        *change_lines,
        "",
        "## Validation",
        f"- Reproduction reproduced: `{repro.get('reproduced')}`",
        *_validation_rows(run),
        "",
        "## Sandbox fidelity",
        f"- Score: `{fidelity.get('score')}`",
        f"- Material gaps: {fidelity_text}",
        "",
        "## Risk and blast radius",
        rationale.get("risk_notes")
        or "Config/manifest-scoped change within allowlisted paths; draft PR only.",
        "",
        "## Rollback",
        rationale.get("rollback_notes")
        or "Revert this PR / restore files to the failing commit contents.",
        "",
        "## Audit link",
        f"- **result_id:** `{result_id}`",
        f"- **sandbox_id:** `{sandbox_id}`",
        f"- **run_id:** `{run.get('run_id')}`",
        "",
        "---",
        "_Generated by Raphael. Explanations may include model-assisted text; "
        "validation results are machine-executed. Do not merge without human review._",
    ]
    return "\n".join(sections) + "\n"
