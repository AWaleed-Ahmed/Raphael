# Raphael Sandbox — detailed usage guide

This document is the **how-to** for the sandbox subsystem: install tools, start the controller, run tests, call the API, and configure environment variables.

For product context (what Raphael is), see the [root README](../README.md).

---

## What the sandbox does

The sandbox controller is a typed HTTP service that gives a future agent a safe place to:

1. Create an isolated namespace for a run  
2. Deploy YAML / Helm / Kustomize at a failing commit  
3. Observe a deterministic failure signature  
4. Redeploy a candidate fix and re-observe  
5. Run validation (commands, rollout, HTTP, signature compare)  
6. Freeze an immutable `result_id` (`finalize`) for a later PR step  
7. Destroy the namespace (idempotent)

It never opens GitHub PRs and never mutates production.

Layout:

```text
sandbox/
  controller/   # Rust Axum service (cargo)
  tests/        # Manual feature / stress / break suite (Python + httpx)
  harness/      # Failure scenarios + contract tests
  kind/         # kind cluster bootstrap scripts
  fixtures/     # Synthetic secrets + expected signatures
contracts/sandbox/   # Frozen JSON Schema (repo root)
```

---

## Prerequisites

| Tool | Why | Notes |
|------|-----|--------|
| Rust / Cargo | Build controller | Stable toolchain |
| Python 3.11+ | Manual tests | venv under `sandbox/tests/.venv` (gitignored) |
| Docker | kind only | `docker info` must work for your user |
| kubectl, kind, helm | kind backend | Install to `~/.local/bin` |

```bash
export PATH="$HOME/.local/bin:$PATH"

# Optional: install Docker (needs sudo password once)
sudo bash sandbox/kind/install-docker.sh
sudo usermod -aG docker "$USER"
# then re-login or: newgrp docker
docker info
```

---

## 1. Mock backend (no Docker)

Fastest path. Signatures and policy are deterministic; no real cluster.

### Terminal 1 — start controller

```bash
cd ~/Documents/work/Projects/Raphael
export PATH="$HOME/.local/bin:$PATH"

RAPHAEL_CLUSTER_BACKEND=mock \
RAPHAEL_LISTEN=127.0.0.1:8090 \
  cargo run --manifest-path sandbox/controller/Cargo.toml
```

Wait until logs show listening on `127.0.0.1:8090`.

### Terminal 2 — tests venv + run suite

```bash
cd ~/Documents/work/Projects/Raphael
export PATH="$HOME/.local/bin:$PATH"

# first time only
python3 -m venv sandbox/tests/.venv
sandbox/tests/.venv/bin/pip install httpx

# all tests (default URL http://127.0.0.1:8090)
sandbox/tests/.venv/bin/python sandbox/tests/test.py

# list features / cases
sandbox/tests/.venv/bin/python sandbox/tests/test.py --list

# one feature
sandbox/tests/.venv/bin/python sandbox/tests/test.py health
sandbox/tests/.venv/bin/python sandbox/tests/test.py create
sandbox/tests/.venv/bin/python sandbox/tests/test.py p2

# several + stop on first failure
sandbox/tests/.venv/bin/python sandbox/tests/test.py deploy observe validate --failfast

# filter by case name substring
sandbox/tests/.venv/bin/python sandbox/tests/test.py observe -k probe
```

---

## 2. Kind backend (real local Kubernetes)

### Bootstrap cluster (once / idempotent)

```bash
cd ~/Documents/work/Projects/Raphael
export PATH="$HOME/.local/bin:$PATH"

./sandbox/kind/bootstrap.sh
# creates cluster "raphael-sandbox", context kind-raphael-sandbox, kubeconfig

kubectl --context kind-raphael-sandbox get ns
```

### Terminal 1 — controller on kind

```bash
cd ~/Documents/work/Projects/Raphael
export PATH="$HOME/.local/bin:$PATH"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
export RAPHAEL_KUBE_CONTEXT=kind-raphael-sandbox

RAPHAEL_CLUSTER_BACKEND=kind \
RAPHAEL_LISTEN=127.0.0.1:8090 \
  cargo run --manifest-path sandbox/controller/Cargo.toml
```

### Terminal 2 — full suite against kind

```bash
cd ~/Documents/work/Projects/Raphael
export PATH="$HOME/.local/bin:$PATH"

RAPHAEL_SANDBOX_URL=http://127.0.0.1:8090 \
  sandbox/tests/.venv/bin/python sandbox/tests/test.py
```

**Port note:** default listen is **8090**, not 8080. With no kubeconfig, plain `kubectl` falls back to `http://127.0.0.1:8080`. If the Raphael controller binds there, create fails with `cluster_unavailable … (post namespaces)`.

---

## 3. Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAPHAEL_CLUSTER_BACKEND` | `mock` | `mock` \| `kind` \| `kubectl` \| `kubeconfig` |
| `RAPHAEL_LISTEN` | `127.0.0.1:8090` | HTTP bind address |
| `RAPHAEL_KUBE_CONTEXT` | `kind-raphael-sandbox` when backend=`kind` | kubectl context |
| `KUBECONFIG` | `~/.kube/config` | kubeconfig path |
| `RAPHAEL_SANDBOX_URL` | `http://127.0.0.1:8090` | Test client base URL |
| `RAPHAEL_DATA_DIR` | `.raphael-data` | Durable metadata root |
| `RAPHAEL_SQLITE_PATH` | `$RAPHAEL_DATA_DIR/sandboxes.db` | Points store at sibling `sandboxes/` JSON docs |
| `RAPHAEL_ARTIFACT_DIR` | `.raphael-artifacts` | On-disk artifacts |
| `RAPHAEL_ARTIFACT_RETENTION_HOURS` | `48` | Artifact GC window |
| `RAPHAEL_PSA_ENFORCE` | `restricted` | Namespace PSA enforce level |
| `RAPHAEL_INJECT_RESTRICTED_SC` | `1` | Inject restricted pod `securityContext` on apply (`0` to disable) |
| `RAPHAEL_DEFAULT_WORKSPACE` | unset | Fallback workspace if deploy omits `workspace_path` / clone |
| `RAPHAEL_FIXTURES_DIR` | `sandbox/fixtures/secret_fixtures` | Synthetic secret fixtures |
| `RAPHAEL_KIND_CLUSTER` | `raphael-sandbox` | kind cluster name (bootstrap script) |

Example with explicit data dirs:

```bash
RAPHAEL_CLUSTER_BACKEND=mock \
RAPHAEL_LISTEN=127.0.0.1:8090 \
RAPHAEL_DATA_DIR=/tmp/raphael-data \
RAPHAEL_ARTIFACT_DIR=/tmp/raphael-art \
  cargo run --manifest-path sandbox/controller/Cargo.toml
```

---

## 4. HTTP API

Base URL: `http://127.0.0.1:8090` (unless you changed `RAPHAEL_LISTEN`).

| Verb | Method | Path |
|------|--------|------|
| health | `GET` | `/health` |
| create_sandbox | `POST` | `/v1/sandboxes` |
| deploy_revision | `POST` | `/v1/sandboxes/{id}/deploy` |
| observe_failure | `POST` | `/v1/sandboxes/{id}/observe` |
| run_validation | `POST` | `/v1/sandboxes/{id}/validate` |
| finalize_result | `POST` | `/v1/sandboxes/{id}/finalize` |
| get result | `GET` | `/v1/sandboxes/{id}/result` |
| destroy_sandbox | `POST` | `/v1/sandboxes/{id}/destroy` |
| admin force-cleanup | `POST` | `/v1/admin/force-cleanup` |

Schemas: [`contracts/sandbox/`](../contracts/sandbox/).

### Curl examples

```bash
# health
curl -s http://127.0.0.1:8090/health

# create
curl -s -X POST http://127.0.0.1:8090/v1/sandboxes \
  -H 'content-type: application/json' \
  -d '{
    "run_id": "demo-1",
    "tenant_id": "local-dev",
    "repository": {"owner": "raphael", "name": "demo"},
    "commit_sha": "abcdef1234567",
    "timeout_minutes": 20,
    "secret_fixture_set": "payments-test"
  }'

# destroy (replace SANDBOX_ID)
curl -s -X POST http://127.0.0.1:8090/v1/sandboxes/SANDBOX_ID/destroy \
  -H 'content-type: application/json' \
  -d '{"reason":"manual"}'

# admin cleanup
curl -s -X POST http://127.0.0.1:8090/v1/admin/force-cleanup \
  -H 'content-type: application/json' \
  -d '{"sandbox_id":"SANDBOX_ID","reconcile_leaks":true,"reason":"ops"}'
```

### Typical lifecycle

```text
create → deploy(broken) → observe → deploy(fixed) → observe → validate → finalize → GET result → destroy
```

`finalize` freezes an immutable validated-fix record and returns `result_id`. Sandbox does **not** open a GitHub PR — that is later agent work.

### Manifest types on deploy

```json
{ "manifests": { "type": "yaml", "path": "deploy/manifests" } }
{ "manifests": { "type": "helm", "chart": "deploy/chart", "values": ["deploy/chart/values.yaml"], "release_name": "payments" } }
{ "manifests": { "type": "kustomize", "overlay": "deploy/overlays/staging" } }
```

Scenarios live under `sandbox/harness/scenarios/`.

### HTTP health check URL form

For real clusters, validation can probe a Service via port-forward:

```json
{ "type": "http", "url": "svc/payments-api:80/", "expected_status": 200, "timeout_seconds": 60 }
```

Also supports `http://127.0.0.1:...` / `localhost`.

---

## 5. Manual test features

| Feature | What it covers |
|---------|----------------|
| `health` | `/health` + spam |
| `create` | happy path, bad inputs, duplicate run |
| `destroy` | idempotent destroy, unknown id, stress ×20 |
| `deploy` | YAML deploy, missing paths/types, redeploy |
| `observe` | signature classes, empty observe, match flag |
| `validate` | pass after fix, fail-closed, still-broken |
| `finalize` | freeze result, clear on redeploy |
| `helm` | Helm probe reproduce + missing chart |
| `kustomize` | overlay reproduce + missing overlay |
| `policy` | privileged / hostPath blocked, fidelity gaps |
| `p0` | clone-at-SHA, fixtures, artifacts |
| `p1` | early liveness, Helm schema fail, Kustomize broken ref, `full_validation`, HTTP svc/ |
| `p2` | disk artifacts, force-cleanup, durable store, parallel create/destroy |
| `pipeline` | full e2e, serial ×5, parallel ×4 |

More detail: [`tests/README.md`](tests/README.md).

---

## 6. Harness / contract tests (optional)

```bash
cd sandbox/harness
python3 -m venv .venv
source .venv/bin/activate
pip install httpx jsonschema pytest
# with controller already running on mock:
pytest -q
```

---

## 7. Kind cluster ops

```bash
export PATH="$HOME/.local/bin:$PATH"

kind get clusters
kubectl --context kind-raphael-sandbox get ns
kubectl --context kind-raphael-sandbox get pods -A

# tear down cluster (destructive)
kind delete cluster --name raphael-sandbox
```

---

## 8. Build / check (Rust)

```bash
cargo check --manifest-path sandbox/controller/Cargo.toml
cargo test --manifest-path sandbox/controller/Cargo.toml
# if crates.io is flaky and deps are already cached:
cargo check --offline --manifest-path sandbox/controller/Cargo.toml
```

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `cluster_unavailable … (post namespaces)` | Controller on `:8080` or no kubeconfig; kubectl hit Raphael | Use `:8090`; run `./sandbox/kind/bootstrap.sh`; set `RAPHAEL_KUBE_CONTEXT` |
| `docker.sock` permission denied | User not in `docker` group | `sudo usermod -aG docker $USER` then `newgrp docker` |
| Tests `Connection refused` | Controller not running | Start cargo run; check `RAPHAEL_SANDBOX_URL` |
| Validate `ReadTimeout` | Rollout wait longer than client timeout | Client default is 180s; ensure images pull; check pods with kubectl |
| PSA / pod crashes on kind | Restricted profile | Ensure inject is on (`RAPHAEL_INJECT_RESTRICTED_SC=1`); `kubectl describe pod` |
| Paths not found under `sandbox/controller` | Relative paths from wrong cwd | Run from repo root or use absolute paths |

---

## 10. Related docs

| Doc | Purpose |
|-----|---------|
| [Root README](../README.md) | What Raphael is |
| [`prd.md`](../prd.md) | Product requirements |
| [`CODING_RULE.md`](../CODING_RULE.md) | Coding / architecture rules |
| [`decision.md`](../decision.md) | Decision log |
| [`CHECKLIST.md`](CHECKLIST.md) | P0–P2 status |
| [`contracts/sandbox/`](../contracts/sandbox/) | API schemas |
| [`tests/README.md`](tests/README.md) | Test runner cheat sheet |
