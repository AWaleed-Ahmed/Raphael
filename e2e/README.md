# Raphael/Ignis E2E Harness

End-to-end verification that Raphael's dispatch orchestrator and Ignis's
controller+connector binary interoperate over the real HTTP wire protocol.

This harness lives entirely in `raphael/e2e/` and treats Ignis as an external
binary. It never edits or imports files from the public Ignis repository.

## Prerequisites

- Python 3.12+ with the dispatch venv (`~/venvs/raphael-dispatch` in WSL2)
- Ignis release binary (`cargo build --release --locked` in the Ignis checkout)
- Network access to clone `https://github.com/AmazingDude/raphael-e2e-fixture.git`

## Configuration

| Variable | Default | Description |
|---|---|---|
| `E2E_IGNIS_BIN` | *(required)* | Absolute path to `raphael-sandbox-controller` binary |
| `E2E_CLONE_URL` | `https://github.com/AmazingDude/raphael-e2e-fixture.git` | Test fixture repo |
| `E2E_COMMIT_SHA` | `681f137...` | Fixture commit with probe port mismatch |
| `RAPHAEL_MAX_PATCH_ATTEMPTS` | `2` | Patch budget for escalation scenario |
| `E2E_LEASE_TTL_SECONDS` | `60` | Job lease TTL |

## Scenarios

1. **Success** (`e2e-success-*`): Job reaches `fix_finalized`. Asserts Ignis
   called `destroy_sandbox` and removed its cloned workspace from disk.

2. **Escalation** (`e2e-fail-validation-*`): Patches redeploy the original
   broken YAML, so `signature_absent` validation fails every attempt. Asserts
   escalation after exactly `RAPHAEL_MAX_PATCH_ATTEMPTS` patch deploys.

3. **Restart**: Kills the Ignis process mid-job (after `create_sandbox` but
   before terminal), restarts it, and observes whether the job resumes or
   gets terminalized via lease expiry. Reports actual timing.

## Run (WSL2)

```bash
export E2E_IGNIS_BIN="$HOME/ignis-wsl/controller/target/release/raphael-sandbox-controller"
~/venvs/raphael-dispatch/bin/python e2e/run_e2e.py
```
