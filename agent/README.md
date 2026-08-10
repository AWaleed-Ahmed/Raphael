# Raphael Agent (Engineer B)

Phase 3: draft GitHub PR publish from sandbox `result_id` (dry-run by default).

**Still non-goals:** merging PRs, production cluster writes, K8s watcher. LLM diagnosis remains **off by default**.

---

## Layout

```text
agent/
  raphael_agent/
    ingest/ evidence/ diagnosis/ patch/
    publish/                # draft PR body + GitHub REST adapter
    graph/ store/ sandbox_client/ http_api/
    scripts/smoke.py
```

Graph: `ingest → evidence → diagnose → reproduce → patch → validate ⇄ patch → publish_or_escalate`

---

## Setup

```bash
cd agent
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e .
```

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAPHAEL_SANDBOX_URL` | `http://127.0.0.1:8090` | Sandbox controller |
| `RAPHAEL_PUBLISH_MODE` | `dry_run` | `dry_run` \| `live` |
| `RAPHAEL_GITHUB_TOKEN` / `GITHUB_TOKEN` | unset | Required for `live` publish (PAT with `contents:write` + `pull_requests:write`) |
| `RAPHAEL_GITHUB_API_BASE` | `https://api.github.com` | GitHub API |
| `RAPHAEL_GITHUB_BASE_BRANCH` | `main` | PR base branch |
| `RAPHAEL_GITHUB_PR_LABELS` | `raphael,agent-generated` | Best-effort labels |
| `RAPHAEL_DIAGNOSIS_CONFIDENCE_THRESHOLD` | `0.7` | Hypothesis gate |
| `RAPHAEL_LLM_DIAGNOSIS` | `0` | Optional LLM refine |
| `RAPHAEL_MAX_PATCH_ATTEMPTS` | `3` | Patch loop budget |

Optional App JWT (reserved; Phase 3 uses PAT): `RAPHAEL_GITHUB_APP_ID`, `RAPHAEL_GITHUB_INSTALLATION_ID`, `RAPHAEL_GITHUB_APP_PRIVATE_KEY_PATH`.

---

## Smoke path

```bash
cd agent

# Graph + dry-run publish (no GitHub token)
set RAPHAEL_PUBLISH_MODE=dry_run
python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub

pytest -q

# Live draft PR (optional)
# set RAPHAEL_PUBLISH_MODE=live
# set RAPHAEL_GITHUB_TOKEN=ghp_...
# python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub
```

Dry-run sets `pull_request_url` to a GitHub **compare** URL with `raphael_dry_run=1` (no mutation). Live mode creates branch `raphael/<run-id>-<summary>`, commits patch files via Contents API, opens a **draft** PR.

---

## Phase 4 handoff

- Harden budgets/timeouts/cost caps; prompt-injection / untrusted-log tests
- Operator metrics + run timeline polish; demo script under 10–15 minutes
- Optional: App JWT auth, CODEOWNERS reviewers, post-merge outcome tracking (FR-065)
- Still no production writes / no auto-merge
