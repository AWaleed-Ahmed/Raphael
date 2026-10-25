# HTTPS security maintenance validation — 2026-10-25

Candidate branch: `fix/https-security-2026-10-25`, based on Raphael main
`da330ac136fd9119204767106d6a36467ffcb195`. These are local results, not hosted
CI or proof that an existing deployment has been patched.

## Targeted changes

1. Ignis certificate dependencies were updated and its 31 connector tests passed
   before proceeding with Raphael. See Ignis's report with the same filename.
2. Both Python packages now require `certifi>=2026.10.19`. The checksum-pinned
   Pip 26.2.2 bootstrap is shared by the installation guides and every Python
   package-installing CI job. Pip's bundled trust store needs its own update.
3. The frontend requires Node `>=24.22.1 <25`, selects 24.22.1 through `.nvmrc`,
   and enables npm's strict engine check. Core CI now installs that runtime,
   runs the frontend tests and builds the application.
4. Ignis Tokio/Rustls updates followed; no executor contract or release pin was
   changed in Raphael. No application behavior or TLS verification was weakened.

Next 16.4.2 and Sharp 0.35.5 already satisfy the inspected October 14 fixes.
Their versions and all frontend dependency resolutions are unchanged; the npm
lockfile adds only root engine metadata.

## Executed checks

Commands use the new checkout-local `.venv` unless stated otherwise.

| Check | Result |
| --- | --- |
| Checksum-pinned Pip bootstrap | Passed; Pip 26.2.2 installed |
| Fresh `pip install -e agent -e dispatch` | Passed; resolved Certifi 2026.10.23 |
| `pip check` | Passed; no broken requirements |
| `cd agent; ../.venv/bin/python -m pytest -q` | 502 passed, 4 skipped |
| `cd dispatch; ../.venv/bin/python -m pytest -q` | 88 passed |
| Core workflow/eval/wire/kind-assertion/lease unit tests, including the security tests below | 52 passed |
| `npm ci --no-audit --no-fund` with Node 24.22.1 | Passed |
| `npm test` after that clean install | 19 passed, including 3 new runtime checks |
| `npm run build` after that clean install | Passed; legacy Vite and production Next builds |
| `git diff --check` | Passed |

Run the workflow-related tests from the repository root:

```bash
.venv/bin/python -m unittest tools.tests.test_ci_workflows tools.tests.test_security_dependencies evals.test_run_evals e2e.test_wire_harness e2e.test_kind_verification e2e.test_lease_denial
```

### New security test cases

`tools/tests/test_security_dependencies.py` checks:

- Both backend manifests require the patched CA bundle.
- Application Certifi and Pip's separate bundled Certifi do not trust
  `emSign ECC Root CA - G3`; hostname and certificate verification remain enabled.
- Every Python package-installing CI job bootstraps checksum-pinned Pip first.
- Frontend manifest/lockfile, `.nvmrc`, strict engine enforcement and CI runtime agree.

`frontend/tests/runtime-security.test.jsx` checks:

- The backported Brotli block-switch error exists, and valid Brotli round trips.
- TLS rejects fullwidth, leading-zero and shortened IP hosts even with matching
  DNS names, while accepting a canonical address with a matching IP SAN.
- DNS rejects NUL-containing names before resolution.

All three runtime tests failed under the previous Node 24.13.1 and passed under
24.22.1. An old-runtime `npm ci --dry-run --offline --ignore-scripts` was refused
with `EBADENGINE`. The Brotli test checks the backport marker and normal decoding;
it does not execute a memory-corruption exploit. Patched Node still reports
`process.versions.brotli` as `1.2.0`, so that string alone is not a patch check.

## Local environment changes and limits

- The original Raphael `.venv` was updated to Pip 26.2.2 and Certifi 2026.10.19.
  Both its application and Pip CA bundles passed the compromised-root check.
  Its editable source paths and unrelated packages were preserved.
- nvm installed checksum-verified Node 24.22.1 and selected it as the default
  for new shells. Already running processes must be restarted.
- Restricted runs initially could not open loopback sockets. Reruns with local
  socket access passed; no assertions were skipped to obtain those results.
- Python suites report the existing `jsonschema.RefResolver` deprecation.
  npm reports two esbuild lifecycle scripts without `allowScripts` approval;
  the clean-install build nevertheless passed. No approvals were broadened.
- No live provider call, production scan, customer cluster or hosted deployment
  was used. The four agent skips are not claimed as successful live checks.
- Vercel manages patch releases within the selected major. Redeploy and inspect
  the actual deployed Node version; repository configuration cannot certify it.
- Existing Ignis binaries and the old immutable release remain unchanged.
  The candidate optimized binary was rebuilt and passed a temporary loopback
  mock `/health` smoke with HTTP 200; its owned process and state were cleaned up.
  Release the reviewed rebuilt executor and verify the pair before updating
  Raphael's runtime pin. This task did not push, merge, release or redeploy.
- System Brotli/CA packages and external PHP/NGINX infrastructure remain outside
  these source fixes; the earlier Ubuntu advisory still needed evaluation.

## Upstream references

- [Python trust-store and Pip guidance](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576/1)
- [Node 24.22.1 security release and backports](https://nodejs.org/en/blog/release/v24.22.1)
- [Vercel runtime selection](https://vercel.com/docs/functions/runtimes/node-js/node-js-versions)
- [Next.js October 14 fixes](https://nextjs.org/blog/nextjs-security-update-october-14-2026)
