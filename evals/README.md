# Raphael Evaluation Harness

`evals/` turns the known scenarios from `prd.md` §17 into versioned,
machine-scored runs. It invokes `e2e/run_real_job.py` for each manifest, so
dispatch and the external Ignis binary remain real subprocesses and retain the
same dry-run-only safety controls as the cross-repository E2E workflow.

## Run

```bash
export E2E_IGNIS_BIN=/absolute/path/to/raphael-sandbox-controller
python evals/run_evals.py
```

Results, runner logs, and ordered HTTP traces are written under `evals/out/`
by default. Set `EVAL_OUTPUT_DIR` to choose another artifact directory, or use
`--scenario <id>` to run one versioned scenario.

The manifests pin an external fixture repository and a full commit SHA; no
fixture source is copied into this private repository.

Refusal scenarios are first-class evaluations. They can assert a precise
terminal reason, escalation-report fields, no patch/publish outcome, forbidden
patch content, and absence of named secret payloads. An adversarial manifest
may declare `equivalent_to_scenario`; the runner then executes its baseline and
requires identical classification, confidence, generated patch delta, and
terminal outcome.

All six current scenarios are active after real-hook/mock-backend verification
(D-20260927-01). Forbidden-patch rejection remains deferred under PRD §17.8,
not silently counted as coverage.

The original missing-ConfigMap fixture is now an expected escalation, not a
positive fix: it identifies the missing key but supplies no trustworthy value
to insert. The prior mock validation accepted an invented database URL. See
D-20260930-01; probe and bad-image remain the two positive patch scenarios.

Future scenarios marked `blocked_pending_evidence_boundary` remain excluded
from default and CI execution. An explicit `--verify-blocked --scenario <id>`
can gather proof before activation; its report is marked verification-only.
Ordinary explicit selection of a blocked case fails loudly. Reproduction
assertions inspect the signature's boolean `reproduced` flag, not merely the
presence of a signature object (healthy observations also have signatures).

## CRLF render regression

The existing cross-repository workflow accepts `crlf_checkouts=true` on manual
runs. On that disposable runner only, it sets global Git `core.autocrlf=true`
after source checkout, so the real harness fixture clones exercise Windows-style
line endings. Use `ignis_ref` to pin the exact candidate commit.

After the unchanged harness and evaluations run, `python -m evals.verify_rendered_lf`
checks rendered content for all three pinned fixtures, patch content for the
two positive fixes, and absence of a patch for missing-config. Missing or
unexpected evidence or any CRLF content fails loudly; successful checks
write `evals/out/line-endings.json`, included in the existing artifact upload.
This complements, rather than weakens, the scorer's inflated-diff rejection test.
