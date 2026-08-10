# Pilot local preflight (Day 0–1 without a design partner)

Records what can be proven **without** a real partner install. Does **not** satisfy PRD Phase 5 exit (partner permission approval + ≥5 real dry-run failures).

Run:

```bash
cd agent
export RAPHAEL_PARTNER_MODE=dry_run
export RAPHAEL_LLM_DIAGNOSIS=0
python -m raphael_agent.scripts.pilot_local_preflight
```

## Results (2026-08-10)

| Check | Result |
|-------|--------|
| `pilot_go_nogo` | `go=True` |
| `demo_partner` | `success_draft_pr_ready` + `raphael_dry_run=1` |
| `pytest -q` | 83 passed, 2 skipped |
| `metrics` | RunStore aggregates readable |
| Partner secrets / webhook HMAC | **Blocked** — needs partner env |
| SA deny-list audit on prod kubeconfig | **Blocked** — needs partner cluster |
| ≥5 real eligible dry-run failures | **Blocked** — needs partner repo traffic |
| Permission model signed approval | **Blocked** — needs partner |

See [`pilot-week-runbook.md`](pilot-week-runbook.md) for Days 2–5 with a real design partner.
