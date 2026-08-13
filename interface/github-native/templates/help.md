### Raphael commands
Prefix: `{prefix}`  ·  **Mode:** partner={partner_mode} publish={publish_mode}

**Implemented (GH-M1)** — write collaborators:
- `{prefix} status [run_id]` — run summary for this Issue/PR
- `{prefix} help` — this list (no secrets)
- `{prefix} feedback accepted|rejected|edited` — FR-065 feedback only (**never** merges)

**Implemented (GH-M2)** — admin or `RAPHAEL_GITHUB_COMMAND_TEAM`:
- `{prefix} retry [run_id]` — new run from the same fingerprint; sets `parent_run_id`
- `{prefix} escalate [run_id] [notes]` — in-flight → `escalated`/`human_requested`; terminal → notes only

**Deferred (not implemented — GH-M3/M4)** — admin or team:
- `{prefix} cancel` / `{prefix} diagnose` / `{prefix} fix`
- Check Runs (`RAPHAEL_GITHUB_CHECK_RUNS`) — advisory, conclusion `neutral` when enabled later
