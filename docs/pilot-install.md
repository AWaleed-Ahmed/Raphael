# Canonical pilot installation

Updated 2026-10-22. This is the canonical **Linux, loopback, mock-backend,
dry-run** setup. It starts the combined Raphael core and the separate Ignis
controller with its embedded outbound connector. It creates no Kubernetes
cluster and needs no GitHub publishing, provider or Supabase credential.

## 1. Select the staging candidate source pair

| Component | Pinned reference | Meaning |
| --- | --- | --- |
| Raphael | `26e17c0faa2a2eeda8f2855be93a1bb71fcdf17b` | PR #70 Next.js candidate, including main `93cfe34`; frontend build, interaction tests and local HTTP routes/proxy verified. This does not qualify a partner installation. |
| Ignis runtime | `contracts-v1.4.2` → `2bfcc644f278da3e16845d6e4408ee9b6048922d` | Exact executor source to build. |
| Contract snapshot | Raphael `CONTRACTS_VERSION=contracts-v1.4.2` | All 29 vendored sandbox blobs match that release. |

Runtime and contract references were checked independently and match for this
pair. An older branch containing `contracts-v1.3.0` must not be treated as this
candidate checkout. Do not edit the pin to bypass that mismatch: select the
intended Raphael revision first. Future runtime-only releases may legitimately
use different references after explicit paired verification.

Historical backend baseline proof (before this Next.js candidate): [main core](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39369470746),
[main paired mock/kind](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39369470736),
[released-pair CRLF](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39364091364).
Current candidate checks are attached to [PR #70](https://github.com/AWaleed-Ahmed/Raphael/pull/70).
These older runs do not establish current-head or partner-install proof.
See [release milestones](release-milestones-2026-10-18.md) for remaining gates.

## 2. Prerequisites and source access

- These setup commands were executed on Linux. Linux under WSL2 can follow
  the Bash instructions; native Windows checkout/process cancellation was not
  qualified. Real-backend evidence remains limited to the linked Linux kind cases.
- Git, Bash, curl, Python 3.12+ with `venv`/pip, and Rust stable with Cargo.
  Verification used Python 3.12.3 and Rust/Cargo 1.97.1. No lower Rust MSRV is
  qualified here. Building SQLite dependencies needs a working native compiler.
- Optional console: Node.js 24.22.1 or newer 24.x/npm. Use `nvm install` and
  `nvm use` from `frontend/` to select its `.nvmrc` security baseline.
- Docker, kind and kubectl are **not** required for this basic mock setup.
  Real-backend qualification needs an explicitly owned sandbox context; Helm
  and Kustomize are needed only for corresponding renderer paths.

GitHub currently reports the Raphael source repository as public. The core's
private trust boundary is separate from repository visibility. If it is made
private, or the pilot target is private, configure Git access first with an
approved credential helper/SSH agent or `gh auth login` plus `gh auth setup-git`.
Verify read access with `git ls-remote`; never put a token in a clone URL.
The Ignis process must inherit its own Git transport access to target repositories;
`RAPHAEL_GITHUB_TOKEN` is not automatically forwarded to its Git process.

Use new directories; stop if either checkout already exists. Keep an existing
working tree intact and choose another `RAPHAEL_PILOT_ROOT` if needed.

```bash
export RAPHAEL_PILOT_ROOT="$HOME/raphael-pilot"
mkdir -p "$RAPHAEL_PILOT_ROOT"
cd "$RAPHAEL_PILOT_ROOT"
test ! -e raphael && test ! -e ignis
git clone https://github.com/AWaleed-Ahmed/Raphael.git raphael
# Fetch the candidate explicitly while PR #70 is awaiting merge.
git -C raphael fetch origin refs/pull/70/head
git -C raphael checkout --detach 26e17c0faa2a2eeda8f2855be93a1bb71fcdf17b
git clone https://github.com/AWaleed-Ahmed/Ignis.git ignis
git -C ignis checkout --detach contracts-v1.4.2
test "$(git -C ignis rev-parse HEAD)" = 2bfcc644f278da3e16845d6e4408ee9b6048922d
test "$(cat raphael/CONTRACTS_VERSION)" = contracts-v1.4.2
cd raphael
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-bootstrap.txt
python -m pip install -e agent -e dispatch
cargo build --release --locked --manifest-path "$RAPHAEL_PILOT_ROOT/ignis/controller/Cargo.toml"
```

The `test` commands must succeed before continuing; these blocks are interactive
instructions, not an unattended installer. Use `python3` instead of `python3.12`
only after confirming it is Python 3.12+. Both tracked Python packages and the
checkout's `contracts/` and fixtures are needed. This is a source-checkout
installation, not a claim that the agent wheel bundles the complete pilot.

## 3. Create and explicitly load the local profile

The applications **do not automatically load `.env`**. Export configuration in
each process terminal, source an operator-owned shell file, or use a service
manager's environment facility. The file below is outside both Git repositories.
The token strings are deliberately labelled local examples, suitable only for
this loopback exercise. Use distinct generated credentials from the operator's
secrets manager for a customer deployment.

```bash
mkdir -p "$RAPHAEL_PILOT_ROOT/state/agent" "$RAPHAEL_PILOT_ROOT/state/ignis"
cat > "$RAPHAEL_PILOT_ROOT/pilot.env" <<'ENV'
export RAPHAEL_PARTNER_MODE=dry_run
export RAPHAEL_PUBLISH_MODE=dry_run
export RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES=''
export RAPHAEL_LLM_DIAGNOSIS=0 RAPHAEL_LLM_PATCH=0 RAPHAEL_MODEL_ENABLED=0 RAPHAEL_LEARNING=0
export RAPHAEL_GITHUB_COMMANDS=0 RAPHAEL_GITHUB_AUTO_COMMENTS=0 RAPHAEL_GITHUB_CHECK_RUNS=0
export RAPHAEL_AGENT_LISTEN=127.0.0.1:8091
export RAPHAEL_SANDBOX_URL=http://127.0.0.1:8090
export RAPHAEL_DISPATCH_BRIDGE_ENABLED=1
export RAPHAEL_AGENT_DATA_DIR="$RAPHAEL_PILOT_ROOT/state/agent"
export RAPHAEL_AGENT_STORE=json
export RAPHAEL_DISPATCH_TOKENS='{"local-example-producer":{"tenant_id":"local-dev","role":"producer"},"local-example-connector":{"tenant_id":"local-dev","role":"connector","connector_id":"pilot-local-1"}}'
export RAPHAEL_CLUSTER_BACKEND=mock RAPHAEL_LISTEN=127.0.0.1:8090
export RAPHAEL_DATA_DIR="$RAPHAEL_PILOT_ROOT/state/ignis"
export RAPHAEL_CONNECTOR_DISPATCH_URL=http://127.0.0.1:8091
export RAPHAEL_CONNECTOR_CONTROLLER_URL=http://127.0.0.1:8090
export RAPHAEL_CONNECTOR_TENANT_ID=local-dev RAPHAEL_CONNECTOR_TOKEN=local-example-connector
export RAPHAEL_FIXTURES_DIR="$RAPHAEL_PILOT_ROOT/ignis/fixtures/secret_fixtures"
unset RAPHAEL_SECRET_FIXTURE_SET
unset GITHUB_TOKEN RAPHAEL_GITHUB_TOKEN RAPHAEL_GITHUB_APP_ID RAPHAEL_GITHUB_INSTALLATION_ID
unset RAPHAEL_GITHUB_APP_PRIVATE_KEY RAPHAEL_GITHUB_APP_PRIVATE_KEY_PATH RAPHAEL_AUTO_MERGE
unset SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY SUPABASE_SECRET_KEY
unset RAPHAEL_INTERFACE_TOKEN RAPHAEL_GITHUB_WEBHOOK_SECRET
ENV
chmod 600 "$RAPHAEL_PILOT_ROOT/pilot.env"
source "$RAPHAEL_PILOT_ROOT/pilot.env"
```

| Configuration | Purpose and source |
| --- | --- |
| Dispatch tokens | Operator-issued bearer mapping. Producer submits to `POST /v1/tenants/local-dev/jobs`; connector polls `GET /v1/tenants/local-dev/jobs/next`, posts `/v1/results`, and renews the current job lease. Tenant/role must match. Give distinct connectors distinct credentials/identity. |
| Connector URLs | Dispatch URL is the **core base URL**, not a `/jobs/next` or WebSocket URL. Controller URL is the local executor base URL. Defaults: poll 1000 ms, dispatch HTTP timeout 30 s. |
| Bridge | Same-process webhook-to-dispatch submission through the one shared orchestrator. It needs no internal bearer token. A bridge event still needs a clone URL and commit SHA. |
| Persistence | Agent JSON by default, optional `RAPHAEL_AGENT_STORE=sqlite`. Ignis uses its own data directory and SQLite/recovery journal. Preserve directories across restart; do not run multiple core instances against the same store. Persisted leases exist; horizontal scaling is not qualified. Executable patch bytes are not durable, so some restarts fail closed. |
| Secret fixtures | Path makes approved fixture definitions available; it does not select one. Selection is an explicit operator decision via `RAPHAEL_SECRET_FIXTURE_SET`. Never infer approval from a Secret name. |
| Local inference | Merged [#59](https://github.com/AWaleed-Ahmed/Raphael/pull/59) defaults the flag to `0`; this profile also explicitly sets `0`. The ignored prediction runtime is still absent from clean checkouts. #40 remains open despite delivery of the deferral path. |
| Customer webhook HMAC | Obtain/generate in the authorized GitHub webhook/App configuration; set `RAPHAEL_GITHUB_WEBHOOK_SECRET` in the core service environment and GitHub. Unset is permitted only for this local exercise. |
| Interface bearer | `RAPHAEL_INTERFACE_TOKEN` protects I0 APIs; loopback can omit it when unset. Non-loopback requires a configured matching token. It is distinct from dispatch tokens and webhook HMAC. |

Keep defaults on loopback. The controller and legacy dispatch operations are
not a hardened public ingress; do not expose them to customers/the Internet.
A customer installation requires reviewed TLS, ingress authentication and
network policy. These instructions do not provision that infrastructure.

## 4. Start the two processes

In **Terminal A**, reload the profile and run the combined server from the
Raphael repository root. An agent-only `uvicorn ...http_api.app:app` command
omits dispatch and is not the complete pilot deployment.

```bash
export RAPHAEL_PILOT_ROOT="$HOME/raphael-pilot"
source "$RAPHAEL_PILOT_ROOT/pilot.env"
source "$RAPHAEL_PILOT_ROOT/raphael/.venv/bin/activate"
cd "$RAPHAEL_PILOT_ROOT/raphael"
python run.py
```

In **Terminal B**, run the released controller/embedded connector. This binary
owns its local mock work and outbound polling; no third connector service is needed.

```bash
export RAPHAEL_PILOT_ROOT="$HOME/raphael-pilot"
source "$RAPHAEL_PILOT_ROOT/pilot.env"
cd "$RAPHAEL_PILOT_ROOT"
"$RAPHAEL_PILOT_ROOT/ignis/controller/target/release/raphael-sandbox-controller"
```

If a port is occupied, stop only a process you own or select different bind
ports and update **all** matching URLs in the profile. Do not kill an unrelated
service. These foreground commands intentionally run until Ctrl+C.

## 5. Check health, authentication and offline smoke

In **Terminal C**, load the same root/profile and activate the virtual environment.

```bash
export RAPHAEL_PILOT_ROOT="$HOME/raphael-pilot"
source "$RAPHAEL_PILOT_ROOT/pilot.env"
source "$RAPHAEL_PILOT_ROOT/raphael/.venv/bin/activate"
curl --fail http://127.0.0.1:8091/health
curl --fail http://127.0.0.1:8090/health
curl --fail -H 'Authorization: Bearer local-example-connector' http://127.0.0.1:8091/v1/tenants/local-dev/jobs/next
curl --fail http://127.0.0.1:8091/v1/pilot/go-nogo
cd "$RAPHAEL_PILOT_ROOT/raphael/agent"
python -m raphael_agent.scripts.pilot_go_nogo
python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub
python -m raphael_agent.scripts.metrics
```

Expected: both health routes return 200 JSON; the core includes `ok=true` and
Ignis `status=ok`. An empty queue returns `messages=[]`, `pending=false`.
Missing poll credentials return 401; another tenant with this token returns 403.
Go/no-go returns `go=True` for the safe environment. It checks configuration,
not customer readiness. Recorded smoke reports `success_draft_pr_ready`,
`res-recorded-001` and a comparison URL containing `raphael_dry_run=1`.
It uses recorded sandbox responses, not the running Ignis process or Kubernetes.
Metrics report the current store's aggregates, not proof of a submitted real job.

For a stronger **real-process/mock-Kubernetes** check, stop A and B
first and let the existing harness own its processes and fixtures:

```bash
cd "$RAPHAEL_PILOT_ROOT/raphael"
E2E_IGNIS_BIN="$RAPHAEL_PILOT_ROOT/ignis/controller/target/release/raphael-sandbox-controller" python -u e2e/run_real_job.py
```

This harness requires Git read access to its pinned public fixture repository.
It is not an offline check: its default Service/port scenario may safely escalate
rather than repair. Success means the harness accepts the scoped terminal result,
not that every input is fixed. It was inspected, not executed in this refresh.
This is distinct from real-kind and partner proof. See
[local verification](pilot-local-preflight.md) for actual executed results and limits.

## 6. Optional local console

Demo mode needs no API or credentials:

```bash
cd "$RAPHAEL_PILOT_ROOT/raphael/frontend"
npm ci
npm run dev -- --hostname 127.0.0.1 --port 5173
```

For live loopback API data, use a local development proxy. The shipped core does
not add general browser CORS headers, so pointing a different-origin browser
straight at `http://127.0.0.1:8091` is not the canonical setup. Keep the core's
interface token unset for this loopback exercise and do not set a browser token.

Stop the demo console server before starting the proxy configuration. In Bash:

```bash
cd "$RAPHAEL_PILOT_ROOT/raphael/frontend"
RAPHAEL_DEV_API_PROXY=true VITE_RAPHAEL_API_URL=/api npm run dev -- --hostname 127.0.0.1 --port 5173
```

For the optional console on a PowerShell host with the source already checked out:

```powershell
Set-Location "$env:RAPHAEL_PILOT_ROOT/raphael/frontend"
$env:RAPHAEL_DEV_API_PROXY = "true"
$env:VITE_RAPHAEL_API_URL = "/api"
npm run dev -- --hostname 127.0.0.1 --port 5173
```

The PowerShell example covers only frontend configuration; it does not qualify
native Windows Ignis execution. Both variables may instead be set in
`frontend/.env.local`. Restart the dev command after changing them: it builds
the legacy console with Vite before starting Next.js. Next's development-only
rewrite forwards `/api/*` to `http://127.0.0.1:8091/*`; production builds do not
enable this loopback proxy.

Open `http://127.0.0.1:5173/console/`; `/` serves the landing page.
`curl --fail http://127.0.0.1:5173/api/v1/runs` should return the core's JSON,
not demo data. Vite embeds `VITE_*` values into the console bundle; these values
are browser-visible. Its environment loading is independent of Python.
Never put a production bearer, provider key or Supabase backend key in them.
Nonlocal console use requires a separately reviewed authenticated server-side
proxy. Full browser/user-journey acceptance remains pending.

## 7. Separate optional qualification and partner work

- **Real Kubernetes:** use only explicitly owned sandbox kubeconfig/context and
  reviewed Ignis procedures. The existing hosted workflow creates disposable
  kind clusters; no cluster provision is part of this guide's basic setup.
- **Supabase:** not needed for the basic probe smoke. [Supabase setup](../supabase/README.md)
  requires a pre-authorized project, applied migrations and backend-only credentials.
  Live healthy-baseline write/read/repair and wrong-scope controls remain unqualified.
  Missing catalog configuration causes localization to skip safely.
- **BYOK:** implemented providers and precedence are in the
  [provider guide](https://github.com/AWaleed-Ahmed/Raphael/blob/0dc46c47b976a42dd958ad4d8e56dcfaf8b154ab/docs/byok-provider-guide.md). All model paths remain off here.
  Merged [#58](https://github.com/AWaleed-Ahmed/Raphael/pull/58) records bounded pinned
  Gemini qualification on an earlier snapshot; corrected automatic selection
  has no successful live rerun. No provider call is part of installation.
- **GitHub integration:** inbound events use `/v1/webhooks/github`; configure
  HMAC and authorized repository events before real traffic. GitHub commands,
  comments and advisory Checks require separate permission review. A dry-run
  repair setting does not prohibit all comment/label mutations when those
  optional features are enabled, so they remain off in this profile.
- **Live drafts:** a separate approved step requires partner `allowlist`,
  publish `live`, a nonempty class allowlist and scoped GitHub credentials.
  Prefer read-only source access for dry-run; request write permissions only
  for authorized branch/commit/draft publication. No auto-merge or production writes.
- **Partner acceptance:** [acceptance checklist](pilot-acceptance.md) and
  [milestone runbook](pilot-week-runbook.md) require permission approval and at
  least five real eligible dry-run failures; a local `go=True` is insufficient.

## 8. Shutdown and owned-resource cleanup

Wait for submitted work to reach terminal and confirm connector cleanup before
stopping services. Stop Vite and Ignis with Ctrl+C in their own terminals, then
stop the core and run `deactivate` in shells using the virtual environment.
Stopping the core alone does not establish that active work was cancelled.

This basic profile creates no cluster. Keep `state/agent`, `state/ignis`, any
artifact directories and verification logs until evidence/recovery is no longer
needed. Remove only the pilot root you created after inspecting it and confirming
no owned jobs/processes remain. Real-backend namespaces must be cleaned up by the
owned executor/harness procedure before discarding its recovery journal; do not
substitute arbitrary production `kubectl delete` operations.

## 9. Supabase localization qualification boundary

Leave `RAPHAEL_HEALTHY_CATALOG_ENABLED=0` for the basic pilot. Setting Supabase
credentials does not qualify or enable healthy-baseline localization. Explicit
opt-in additionally requires both fixed backend `RAPHAEL_COMPANY_ID` and
`RAPHAEL_CLIENT_ID`; request-supplied scope cannot override them. Live ingestion,
actual JWT HTTP access, image repair and production localization benefit remain
deferred. SQL-role tenant isolation passed the
[database checks](supabase-migration-validation-2026-10-20.md) with simulated claims.
The [dated qualification procedure](supabase-localization-qualification-2026-10-20.md)
provides test-project migration/JWT/workload inputs, a credential-gated harness,
and exact cleanup. Its direct fixture seeding is not production ingestion.
