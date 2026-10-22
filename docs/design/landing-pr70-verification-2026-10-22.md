# PR #70 install compatibility verification — 2026-10-22

Qualified runtime source: `26e17c0faa2a2eeda8f2855be93a1bb71fcdf17b`, merging
main `93cfe3442262a34cac3c9160bacda5fe2fb7e6ef` into contributor head
`aba110742b67280e8559dfcb57d28608b58067e1`. The merge had no conflicts;
new main changes preserve authenticated feedback and rejection of unsupported
delete patch proposals. The subsequent documentation commit changes no runtime code.

## Completed corrections

- Root README and canonical pilot guide use Next's `--hostname` and `--port`
  options and open `/console/`; `/` remains the landing page.
- The old Vite `--config` proxy recipe is replaced with the implemented
  development-only `RAPHAEL_DEV_API_PROXY=true` opt-in and browser-visible
  `VITE_RAPHAEL_API_URL=/api`, with Bash and PowerShell examples.
- The pilot source reference selects the Next.js candidate. The older backend
  baseline runs remain explicitly historical rather than claimed as new proof.
- Contributor fixes add six directly selectable repair stages in both motion
  modes and keep the blocking intro out of initial server HTML.

## Expected and actual checks

| Check | Expected | Actual |
| --- | --- | --- |
| Existing frontend tests, executed with node --import tsx | All interactions/configuration pass | 16 named tests pass at aba1107; frontend runtime files unchanged by main sync/docs |
| npm run build | Legacy Vite console and Next landing compile | Pass at aba1107; same frontend sources/dependencies after main sync |
| Canonical dev startup with --hostname 127.0.0.1 --port 5173 | Server starts | Pass on merged source |
| node tests/routes.mjs http://127.0.0.1:5173 | Landing, console, script assets and direction load; initial HTML contains no intro overlay | All pass on merged source |
| Real loopback HTTP proxy | /api/v1/runs, query parameters and /api/health reach backend paths | All pass against an owned synthetic API fixture; correct path/query and JSON response |
| PYTHONPATH=agent:dispatch python -m pytest -q agent/tests/test_feedback.py agent/tests/test_patch.py agent/tests/test_byok.py | Synced security changes preserve behavior | 151 passed, one existing Starlette/AnyIO deprecation warning |
| git diff --check | No new whitespace errors | Pass |

No browser inspection, remote provider calls or customer credentials were used.
The API fixture is not a partner backend; this does not qualify live console
user journeys, native Windows Ignis execution, or a partner installation.
Temporary development/fixture servers are stopped after verification.
Hosted current-head checks remain required on the PR; do not merge from local
results alone.
