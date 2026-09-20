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
