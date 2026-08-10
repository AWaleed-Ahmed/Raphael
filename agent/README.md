# Raphael Agent (Engineer B)

Phase 5: pilot readiness — partner dry-run default, failure-class allowlist for live draft PRs.

**Still non-goals:** auto-merge, production cluster writes, K8s watcher. LLM **off** by default.

Pilot docs: [`docs/pilot-install.md`](../docs/pilot-install.md) · [`docs/permission-matrix.md`](../docs/permission-matrix.md) · [`docs/pilot-acceptance.md`](../docs/pilot-acceptance.md)

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

Live draft PR only when: `PARTNER_MODE=allowlist` **and** `PUBLISH_MODE=live` **and** class allowlisted **and** token present.

---

## Partner dry-run demo (≤15 min)

```bash
cd agent
python -m raphael_agent.scripts.demo_partner
# or:
# set RAPHAEL_PARTNER_MODE=dry_run
# python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub

pytest -q
python -m raphael_agent.scripts.metrics
```

Expect `status=success_draft_pr_ready`, `result_id`, `pull_request_url` with `raphael_dry_run=1`.

---

## Flip one class to live draft (after security review)

```bash
$env:RAPHAEL_PARTNER_MODE="allowlist"
$env:RAPHAEL_PUBLISH_MODE="live"
$env:RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES="probe_misconfiguration"
$env:RAPHAEL_GITHUB_TOKEN="ghp_..."
```

---

## What’s left for a real pilot week

See [`docs/pilot-acceptance.md`](../docs/pilot-acceptance.md): partner secrets, SA deny-list verification, ≥5 real dry-run failures, optional single-class live allowlist, feedback capture.
