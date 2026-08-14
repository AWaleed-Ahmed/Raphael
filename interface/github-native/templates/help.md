### Raphael commands
Prefix: `{prefix}`  ·  **Mode:** partner={partner_mode} publish={publish_mode}

**Implemented (GH-M1)** — write collaborators:
- `{prefix} status [run_id]` — run summary for this Issue/PR
- `{prefix} help` — this list (no secrets)
- `{prefix} feedback accepted|rejected|edited` — FR-065 feedback only (**never** merges)

**Implemented (GH-M2)** — admin or `RAPHAEL_GITHUB_COMMAND_TEAM`:
- `{prefix} retry [run_id]` — new run from the same fingerprint; sets `parent_run_id`
- `{prefix} escalate [run_id] [notes]` — in-flight → `escalated`/`human_requested`; terminal → notes only

**Deferred (not implemented)** — admin or team:
- `{prefix} cancel` / `{prefix} diagnose` / `{prefix} fix`

**Check Runs (GH-M4)** — opt-in, default off (does not inherit commands):
- Enable with `RAPHAEL_GITHUB_CHECK_RUNS=1`. Name: `Raphael (advisory)`. Conclusion defaults to `neutral`.
- Optional `RAPHAEL_GITHUB_CHECK_ADVISORY_SUCCESS=1` may use `success` on draft-ready / snippet terminals only.
- Advisory only — never a required merge check, never a Merge action.
