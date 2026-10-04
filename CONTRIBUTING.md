# Contributing to Raphael

Start with [handoff.md](handoff.md): it maps the two repositories, verified
capabilities, current release pins, open tasks, and safe parallel work.
[prd.md](prd.md) defines the product; [CODING_RULE.md](CODING_RULE.md) defines
the safety and coding rules. The public executor lives in
[Ignis](https://github.com/AWaleed-Ahmed/Ignis), not inside this checkout.

## Setup

Use Python 3.12+ and Rust/Cargo in Linux or WSL2. WSL2 avoids the native
Windows pytest-temp ACL and linker problems seen on this machine. Ask before
privileged installation or destructive operations.

The commands assume new `~/src/raphael` and `~/src/ignis` directories. If
you already have them, use a clean checkout or choose other paths consistently;
do not delete existing work. Configure private-repo Git authentication inside
WSL before cloning; a Windows CLI login alone is not a guarantee it is wired.

```bash
mkdir -p ~/src ~/venvs
cd ~/src
git clone https://github.com/AWaleed-Ahmed/Raphael.git raphael
git clone https://github.com/AWaleed-Ahmed/Ignis.git ignis
python3.12 -m venv ~/venvs/raphael-dispatch
source ~/venvs/raphael-dispatch/bin/activate
cd ~/src/raphael
python -m pip install -e agent -e dispatch
git -C ~/src/ignis checkout contracts-v1.3.0
cargo build --release --locked --manifest-path ~/src/ignis/controller/Cargo.toml
```

The Ignis tag above reproduces the pinned binary. For Ignis development,
branch from fresh main instead. Use [handoff's run instructions](handoff.md#run-locally)
for the combined `run.py` app, connector token configuration, dry-run evals,
and the hosted disposable-kind job. Do not use production credentials.

## Checks before a PR

From the Raphael root with the venv active:

```bash
(cd agent && TMPDIR=/tmp python -m pytest -q)
(cd dispatch && TMPDIR=/tmp python -m pytest -q)
python -m unittest evals.test_run_evals
```

The **read-only contract drift check** is a separate PowerShell 7 prerequisite:

```powershell
# From the Raphael root in an approved PowerShell 7 environment:
pwsh -File tools/sync-sandbox-contracts.ps1 -Check
```

If `pwsh` is absent in WSL, run that same command from a Windows-native
Raphael checkout in PowerShell 7, or rely on hosted `core-ci / contracts`
until an approved local setup is available. The fresh Windows worktree
check passed; Windows PowerShell against the WSL UNC checkout was rejected
by unsigned-script policy. Do not override execution policy or use elevation
as a workaround. Python/Rust installation does not install PowerShell.
This local limitation does not skip the hosted contract gate.

For Ignis changes, from its `controller/` directory:

```bash
cargo fmt --check
cargo check --locked
cargo test --locked
```

Use the existing cross-repo workflow for real-process evals and kind proof,
not a new parallel gate. Hosted checks must pass on the PR head; local
results do not replace them. Traces must not contain live credentials.

## Branch and review checklist

- Inspect `git status`, `git log --oneline -5`, and `git branch --show-current`
  before assuming current behavior. Preserve unrelated dirty work.
- Start from clean, updated main and create a task branch (`feature/*`,
  `fix/*`, or the existing `codex/*` convention). One concern per PR; never
  force-push main/prod. See [branching rules](docs/BRANCHING.md).
- Add both success and refusal/regression tests appropriate to the change.
  A skipped scenario is not a passed safety proof.
- State the actual backend, immutable fixture SHA, flags, publication mode,
  and proof limits. Default automated publishing is dry-run with no token.
- Update handoff/PRD when claims or requirements change. Add a newest-first
  `D-YYYYMMDD-NN` entry to [decision.md](decision.md) for architectural or
  safety decisions; supersede old claims explicitly rather than erase history.
- Public contracts change in Ignis first, with a reviewed immutable release;
  update Raphael's snapshot/pins only as appropriate and run the drift check.
- Never move private Raphael code/configuration into public Ignis, weaken
  secret redaction, override deterministic blocks with models, or give Ignis
  production access. Ask before deleting clusters/files or using `sudo`.
- Open a PR into main, get human review/approval, and wait for required CI.
  Do not merge your own PR without that approval or enable live publishing
  without the separate reviewed confirmation gate.
