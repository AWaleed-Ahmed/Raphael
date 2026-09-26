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

Scenarios marked `blocked_pending_evidence_boundary` are validated as
manifests but excluded from default and CI execution until the documented
dispatch-to-diagnosis evidence boundary exists. Selecting one explicitly fails
loudly rather than treating the blocked case as coverage.
