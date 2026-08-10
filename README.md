# Raphael

Self-healing deployment agent (see `prd.md`).

## Current status

Sandbox subsystem (Engineer A) is implemented under `sandbox/` with frozen contracts in `contracts/sandbox/`.

Coding and architecture rules: [`CODING_RULE.md`](CODING_RULE.md)  
Decision log (why we chose things): [`decision.md`](decision.md)

### Run the sandbox controller (mock backend)

```bash
cd sandbox/controller
RAPHAEL_CLUSTER_BACKEND=mock cargo run
```

### Run harness tests

```bash
cd sandbox/harness
python3 -m venv .venv && source .venv/bin/activate
pip install httpx jsonschema pytest
pytest -q
```

### Run manual feature / stress / break tests (recommended for you)

```bash
# terminal 1
cd sandbox/controller && RAPHAEL_CLUSTER_BACKEND=mock cargo run

# terminal 2
sandbox/tests/.venv/bin/python sandbox/tests/test.py --list
sandbox/tests/.venv/bin/python sandbox/tests/test.py
sandbox/tests/.venv/bin/python sandbox/tests/test.py observe --failfast
```

See [`sandbox/tests/README.md`](sandbox/tests/README.md).

Agent / LangGraph work is intentionally not started until explicitly requested.
