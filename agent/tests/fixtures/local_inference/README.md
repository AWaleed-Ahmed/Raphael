# Public inference qualification inputs

These JSONL fixtures retain adapted public inputs and source provenance from
`raphael/evaluation/results/fresh_hybrid_test/` in the original local checkout;
that ignored evaluation tree is not needed by the packaged runtime or tests.
Old predictions were excluded. Each row has `input`, `expected`, and `source`.

- Classifier, similarity and patch: public GitHub issue reports (50 per model).
  Labels are marker/keyword-derived, not manually verified root causes or fixes.
- Ranker: 50 BugsInPy cases with real fix-file labels and commit URLs. Candidate
  features are derived evaluation inputs, not captured production stack frames.
- Trace: 50 RCAEval measured trace windows around controlled fault injection,
  including adapted healthy-baseline fields. Fault-window labels do not establish
  individual-trace truth.
- Patch has one additional Fission issue (#102), verified against the public
  GitHub API on 2026-10-26. It preserves the full title/body and exercises the
  learned path without an invented normalized reason. No repair label is claimed.

These are public-data runtime checks. They do not establish production accuracy,
tenant isolation, successful sandbox repairs, or training-set independence by
an independent data audit. No training files are copied into the install test.
See `docs/local-inference-runtime.md` for reproduction and interpretation.
