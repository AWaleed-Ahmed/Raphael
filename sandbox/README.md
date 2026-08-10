# Raphael Sandbox

Ephemeral Kubernetes sandbox subsystem for Raphael (Engineer A).

The future agent talks to this controller only through five typed JSON verbs — never free-form `kubectl`.

## Layout

```text
sandbox/
  controller/   # Rust Axum service
  harness/      # Python scenarios + contract/e2e tests
  kind/         # Shared kind cluster bootstrap (one cluster, many namespaces)
  fixtures/     # Synthetic secrets + expected signatures
contracts/sandbox/  # Frozen JSON Schema contracts
```

## Quick start (mock backend — no Docker required)

```bash
# Terminal 1
cd sandbox/controller
RAPHAEL_CLUSTER_BACKEND=mock cargo run

# Terminal 2
cd sandbox/harness
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pytest -q
```

## Kind backend (when Docker is available)

```bash
chmod +x sandbox/kind/bootstrap.sh
./sandbox/kind/bootstrap.sh
RAPHAEL_CLUSTER_BACKEND=kind cargo run --manifest-path sandbox/controller/Cargo.toml
```

## API

| Verb | Method | Path |
|---|---|---|
| health | GET | `/health` |
| create_sandbox | POST | `/v1/sandboxes` |
| deploy_revision | POST | `/v1/sandboxes/{id}/deploy` |
| observe_failure | POST | `/v1/sandboxes/{id}/observe` |
| run_validation | POST | `/v1/sandboxes/{id}/validate` |
| finalize_result | POST | `/v1/sandboxes/{id}/finalize` |
| get result | GET | `/v1/sandboxes/{id}/result` |
| destroy_sandbox | POST | `/v1/sandboxes/{id}/destroy` |

See `contracts/sandbox/` and repo-root `CODING_RULE.md`.
