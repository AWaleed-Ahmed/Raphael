# Raphael Agent (Engineer B)

Phase 5 + pilot week: partner dry-run default, failure-class allowlist, FR-065 feedback audit, guardrail tests.

**Still non-goals:** auto-merge, production cluster writes, K8s watcher. LLM **off** by default.

Pilot docs:

- [`docs/pilot-install.md`](../docs/pilot-install.md)
- [`docs/permission-matrix.md`](../docs/permission-matrix.md)
- [`docs/pilot-acceptance.md`](../docs/pilot-acceptance.md)
- [`docs/pilot-week-runbook.md`](../docs/pilot-week-runbook.md) ← **5-day plan**

---

## Setup

```bash
cd agent
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### Partner / publish env

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAPHAEL_PARTNER_MODE` | `dry_run` | `dry_run` \| `allowlist` \| `diagnosis_only` |
| `RAPHAEL_PUBLISH_MODE` | `dry_run` | Raw preference; gated by partner mode |
| `RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES` | _(empty)_ | Empty ⇒ **no** live PRs; e.g. `probe_misconfiguration` |
| `RAPHAEL_GITHUB_TOKEN` | unset | Required for live draft only |
| `RAPHAEL_GITHUB_REVIEWERS` | unset | Optional reviewer logins |
| `RAPHAEL_LLM_DIAGNOSIS` | `0` | Keep off for pilot unless agreed |
| `RAPHAEL_FEEDBACK_RECORDER` | `jsonl` | `jsonl` \| `off` |
| `RAPHAEL_FEEDBACK_ON_PUBLISH` | unset | `1` to log dry_run_prepared / draft_opened |

Live draft PR only when: `PARTNER_MODE=allowlist` **and** `PUBLISH_MODE=live` **and** class allowlisted **and** token present.

---

## Partner dry-run demo (≤15 min)

```bash
cd agent
python -m raphael_agent.scripts.demo_partner
python -m raphael_agent.scripts.pilot_go_nogo
pytest -q
python -m raphael_agent.scripts.metrics
```

Expect `status=success_draft_pr_ready`, `result_id`, `pull_request_url` with `raphael_dry_run=1`.

---

## Feedback (FR-065 audit)

```bash
python -m raphael_agent.scripts.record_feedback --outcome accepted --run-id ... --notes "lgtm"
python -m raphael_agent.scripts.record_feedback --outcome merged --pr-number 12 --owner raphael --repo demo
# HTTP: POST /v1/feedback
# Webhook: X-GitHub-Event: pull_request (closed/merged/edited) → feedback.jsonl
```

---

## Guardrails

```bash
pytest -q tests/test_guardrails.py tests/test_injection.py tests/test_partner_mode.py tests/test_feedback.py
# HTTP: GET /v1/pilot/go-nogo
```

---

## Flip one class to live draft (after security review)

```bash
$env:RAPHAEL_PARTNER_MODE="allowlist"
$env:RAPHAEL_PUBLISH_MODE="live"
$env:RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES="probe_misconfiguration"
$env:RAPHAEL_GITHUB_TOKEN="ghp_..."
python -m raphael_agent.scripts.pilot_go_nogo
```
