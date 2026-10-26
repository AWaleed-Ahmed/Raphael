# Packaged local inference — issue #63

The runtime is `raphael_agent.local_inference`; it contains prediction,
preprocessing and rules only. Training code and datasets are not distributed.
`ModelGateway` imports it normally, without editing `sys.path` or consulting
an ignored directory, a developer path or the current working directory.

`RAPHAEL_MODEL_ENABLED` remains **0 by default**. The pilot remains disabled.
This delivery qualifies packaging and artifact execution, not tenant-safe
incident retrieval, production accuracy, full graph qualification or rollout.
Those follow-ups remain under #40. No model was retrained or downloaded by the
runtime, and the tracked model bytes are unchanged.

## Install and artifact layout

Qualified on Linux x86-64, CPython 3.12.3, joblib 1.6.0, NumPy 2.5.2,
SciPy 1.18.1 and scikit-learn 1.9.0. The runtime accepts CPython 3.12 with
that exact library set; other Python minors/library versions fail closed.
The manifests record training with joblib 1.5.3 and SciPy 1.18.0. Compatibility
with the qualified newer patch versions was exercised against all five real
bundles; this is not a general cross-version compatibility guarantee.

From the repository root:

```bash
python3.12 -m venv /tmp/raphael-model-env
/tmp/raphael-model-env/bin/python -m pip install --require-hashes -r requirements-bootstrap.txt
/tmp/raphael-model-env/bin/python -m pip install 'setuptools>=68' wheel
/tmp/raphael-model-env/bin/python -m pip install './agent[local-inference]'
cp -R models /tmp/raphael-model-artifacts
```

The wheel contains code, not the model bundles. Deploy only the release-owned
`models/` directory from the same trusted Git revision. Its layout is:

```text
$RAPHAEL_MODEL_ROOT/
  failure_classifier/{manifest.json,model.joblib}
  candidate_ranker/{manifest.json,model.joblib}
  incident_similarity/{manifest.json,model.joblib}
  patch_selector/{manifest.json,model.joblib}
  trace_anomaly/{manifest.json,model.joblib}
```

Set `RAPHAEL_MODEL_ROOT` to an absolute, operator-owned directory. If unset,
the default is `<sys.prefix>/share/raphael/models`; explicitly supplied
`ModelGateway(model_root=...)` takes precedence over the environment.
The runtime never creates the directory or fetches missing files.

For an isolated test from outside the repository (not a pilot configuration):

```bash
cd /tmp
RAPHAEL_MODEL_ENABLED=1 RAPHAEL_MODEL_ROOT=/tmp/raphael-model-artifacts \
  /tmp/raphael-model-env/bin/python -c 'from raphael_agent.model_gateway import ModelGateway; print(ModelGateway().classify_failure({"evidence": [{"summary": "OOMKilled"}]}))'
```

## Trust and failure behavior

Joblib uses pickle and may execute code when deserializing. Never load
customer-provided model files. Hash agreement with a customer-controlled
manifest is insufficient: the package pins independent SHA-256 identities
for **both** each release manifest and its model file in
`agent/raphael_agent/local_inference/artifacts.py`.
See [scikit-learn persistence guidance](https://scikit-learn.org/stable/model_persistence.html).

Before deserialization, the loader checks the qualified dependency versions,
reads a bounded manifest and checks its release hash, then reads at most the
approved artifact size plus one byte and checks its size and release hash.
It deserializes the same in-memory bytes that were checked, preventing a
file-replacement race. Estimator version warnings are errors. Missing,
corrupt, forged or incompatible files produce bounded unavailable reasons
through `model_error`; deterministic execution survives. Exceptions never
include file paths, input evidence or raw deserialization messages.

| Bundle | Bytes | Artifact SHA-256 |
|---|---:|---|
| candidate_ranker | 37018 | `036eca89dc9bb450d665dab516096f8012fb31775f6e187af6a05db2e1cd6b47` |
| failure_classifier | 120859 | `c029aca6c4c0ac197b1e26c444fe2883001a46289101b972b3e181502f5b0d80` |
| incident_similarity | 4456283 | `38115467e972fd9498637e33b5a9cfab3f6e08029af8d09f34bb5b707bc45a41` |
| patch_selector | 269845 | `ed7a9ed3f9713b64bf102e54e734b445b3b6be3e12df8fede4101f6f15741c49` |
| trace_anomaly | 3324 | `b946fabc97bb703b4449595126f2c29872e1a6319559fd2de4410f75c8415020` |

Successful loads reuse a bounded cache of five bundles, keyed by resolved
root and model name. Cached estimators are the verified in-memory objects;
changing files on disk does not replace an already loaded estimator. Restart
the process after an approved deployment change. Failed loads are not cached,
so correcting an unavailable deployment can recover without retraining.
New artifact identities or dependency versions require a reviewed package
change and fresh qualification; replacing a manifest cannot approve them.

## Real public data and interpretation

`agent/tests/fixtures/local_inference/` retains 251 adapted inputs with source
URLs and label provenance, taken from the existing local external-evaluation
cache. None of the training datasets are needed for replay.

| Bundle | Public inputs | Learned execution | Rule overrides | Observed label matches |
|---|---|---:|---:|---:|
| Failure classifier | 50 GitHub failure reports | 50 | 50 | 50/50 |
| Candidate ranker | 50 BugsInPy bug/fix cases | 50 | 0 | 38/50 top-1 fix-file matches |
| Incident similarity | 50 GitHub failure reports | 50 | 0 | 48/50 top-1 class matches |
| Patch selector | 50 GitHub reports + 1 Fission report | 1 | 50 | 47/50 template-hypothesis matches |
| Trace anomaly | 50 RCAEval trace windows | 50 | 15 | 38/50 fault-window matches |

These are measured behavior, not production calibration or causal proof.
GitHub failure labels are marker-derived. Patch labels are keyword-derived
hypotheses and do not prove a working fix. BugsInPy labels identify files in
real fix diffs; they do not prove every changed line caused the bug. RCAEval
contains measured microservice traces around controlled fault injection;
window labels are not manual per-trace labels. Similarity retrieves the
existing bundled index, not a newly constructed production incident store.

The extra [Fission report](https://github.com/fission/fission.io/issues/102)
uses its full title/body and no invented normalized reason. It reaches the
learned template vectorizer/classifier and refuses a low-confidence patch.
A separate component test exercises the learned policy classifier on that
same real evidence and its highest-scoring template; it does not bypass the
runtime confidence threshold or count that refusal as a successful repair.

`learned_execution` reports whether a learned path actually ran. Classifier
and trace rules may override a computed learned score; their rule counts are
reported separately. Patch rule overrides return before learned prediction.
Ranking retains separate learned/evidence scores. Trace results also expose
the original learned probability separately from any rule override.

## Reproduce verification

```bash
/tmp/raphael-model-env/bin/python -m pip install -e './agent[local-inference]' -e ./dispatch
cd agent
/tmp/raphael-model-env/bin/python -m pytest -q
cd ..
/tmp/raphael-model-env/bin/python agent/scripts/qualify_local_inference.py \
  --model-root models --cases-root agent/tests/fixtures/local_inference \
  --output /tmp/local-inference-63.json
```

The installation test builds/installs from a staging tree containing only
`pyproject.toml` and the agent package, deletes that build source, and replays
all 251 inputs through the installed gateway from a temporary directory.
Only approved model bundles and public-input fixtures accompany the install;
no ignored prediction/training tree is present. A Python audit hook rejects
network resolution, connections and binding during runtime import/replay.
It also verifies default-off, the configured model root, missing-artifact
fallback and unchanged `sys.path`.

The loader controls prove that missing files, altered model bytes, oversized
files, changed manifests and jointly forged model/manifest pairs are rejected
before `joblib.load`; incompatible runtime versions, deserialization failure
and unsupported bundle formats also fail safely. Real inference proofs do
not monkeypatch predictions. Fault controls intentionally replace the loader
or version probe to exercise unavailable paths.

The reproducible [replay summary](evidence/local-inference-63.json) records
artifact identities, fixture hashes, prediction digests and execution counts.
Core CI installs the qualified extra, runs all agent tests and retains a
fresh replay summary. No live customer data or production resources are used.

## Local verification record — 2026-10-26

- Full agent suite: **523 passed, 4 skipped** (optional integrations).
- Runtime statement coverage: **92%**, artifact loader **100%**.
- Dispatch suite: **88 passed**.
- CI workflow/security/evaluation/wire checks: **52 passed**.
- Strict mypy: **6 source files passed** (inference package and replay script;
  third-party libraries without stubs are ignored). Black, Ruff and diff checks passed.
- Re-running the public-data report reproduced the committed summary byte for byte.

The first local attempts exposed test-environment setup gaps: dispatch was not
installed in editable mode, the repository's verified pip bootstrap had not
been applied, and loopback fixtures needed execution permission. These were
corrected in the isolated environment; no unrelated source was changed. The
initial offline guard also blocked Python SSL class construction, so it was
replaced with an audit hook denying actual network operations. Final checks
above ran after those corrections.
