# Pilot local preflight

Updated 2026-10-20. Follow the [canonical installation](pilot-install.md).
These checks establish local setup behavior, not partner approval or PRD §23.

## Source update before publication

Main advanced to `a614d47e65904d55e085143ab07c1c5358d5d69e` when #58/#59
merged. The canonical guide now selects that revision. Its package manifests,
frontend sources, contract snapshot and Ignis runtime pin are unchanged from
the executed `0dc46c4` installation below; the Python behavior changes have green
[current core](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39369470746)
and [paired E2E](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39369470736).
The fresh local installation was not rerun at the newer revision. Do not
attribute the earlier local execution to the newer SHA.

## Executed checks (2026-10-20)

A clean temporary Git checkout of Raphael `0dc46c47b976a42dd958ad4d8e56dcfaf8b154ab`
was used with a fresh Python 3.12.3 virtual environment and no ignored developer
files. Ignis source was fetched at release commit
`2bfcc644f278da3e16845d6e4408ee9b6048922d`. No production credentials or paid
provider calls were used. Local evidence is under
`/tmp/raphael-roadmap-refresh-20261020/`; temporary files are not durable hosted artifacts.

| Sequence | Result / scope |
| --- | --- |
| `python3.12 -m venv .venv`; `python -m pip install -e agent -e dispatch` | Passed in fresh environment; editable imports subsequently pointed to the clean Git checkout. Standard build isolation was needed; a no-build-isolation shortcut lacked setuptools and was discarded. |
| `cargo build --release --locked --manifest-path controller/Cargo.toml` in released Ignis | Passed with Rust/Cargo 1.97.1 and native compiler; exact release binary built. |
| `npm ci`; `npm run build` in clean frontend | Passed with Node 24.13.1/npm 11.8.0. |
| `python run.py` + released Ignis embedded connector, mock backend | Both owned processes started on free loopback ports and were stopped after checks. |
| Health/auth | Core and executor health 200; authenticated empty poll 200; absent token 401; wrong tenant 403; run list and go/no-go HTTP 200. No job was submitted. |
| Vite development proxy with `VITE_RAPHAEL_API_URL=/api` | Passed: `/api/v1/runs` returned core JSON with HTTP 200 using the documented proxy configuration on free loopback ports. Owned Vite process group stopped afterward; no browser journey asserted. |
| `python -m raphael_agent.scripts.metrics` | Passed: readable empty-store aggregates (`runs_total=0`). |
| `python -m raphael_agent.scripts.pilot_go_nogo` | `go=True` with explicit dry-run, model/LLM/learning off. Environment posture only. |
| `python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub` | `success_draft_pr_ready`, `res-recorded-001`, dry-run comparison URL. Recorded responses, not real Ignis repair evidence. |

The isolated install used no developer test dependencies. No full test suite or
fresh kind cluster was run for this documentation refresh. Existing hosted
[core](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39366474221),
[paired mock/kind](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39366474138)
and [CRLF qualification](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39364091364)
are separate acceptance evidence. All 29 contract snapshot blobs were compared
with the release via GitHub; this is not execution of the PowerShell checker.

## Inspected and prerequisite-dependent paths

| Sequence | Classification / prerequisite |
| --- | --- |
| Remote Git clones/private credential flow | Commands checked against refs; verification used a local clean Git clone plus GitHub source archive. Private customer access needs authorized Git credentials in each relevant process. |
| `python -u e2e/run_real_job.py` | Inspected only; needs fixture Git access and owns separate processes. Default Service/port case may safely escalate. |
| PowerShell contract checker | Not executed here; needs PowerShell 7. Hosted gate and independent blob comparison are recorded separately. |
| Supabase scripts | Inspected only; needs an approved test project, migrations and backend credentials; writes retained fake rows. |
| Live BYOK | No calls made; earlier scoped Gemini evidence is linked from the roadmap. |
| Customer deployment | Blocked by partner access, reviewed TLS/ingress, webhook HMAC and observer permissions. |
| Full console journey, native Windows, empirical localization/calibration/learning | Not qualified by setup/build checks. |
| Real partner acceptance | Needs permission signoff, ≥5 real eligible dry-runs and human judgments. |

## Documentation checks

All 27 Bash blocks passed `bash -n`; 108 relative file/heading links resolved.
Immutable GitHub documentation links were checked against the selected clean
checkout; issue/PR/run links refer to inspected release evidence. `git diff
--check` passed. PowerShell examples were inspected, not executed here.

## Historical local result (2026-08-10)

The former preflight recorded 83 passed / 2 skipped, readable metrics, `go=True`
and a recorded partner demo. Those counts describe that earlier snapshot; they
are not current test totals or completion of partner acceptance.
