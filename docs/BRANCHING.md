# Git branching (Raphael)

Two-person team. **Do not commit new work straight to `main` or `prod`.**

```text
feature/<name>  ──PR──►  main  ──promote──►  prod
stash/<name>    parked WIP (not a PR target)
```

---

## Branches

| Branch | Purpose | Who updates it |
|--------|---------|----------------|
| **`prod`** | Stable snapshot for demos / partner installs | Promote from `main` only (fast-forward), after tests |
| **`main`** | Integration. Default GitHub branch. PR target | Merge reviewed `feature/*` PRs |
| **`feature/<short-name>`** | All new work | Author; open PR into `main` |
| **`stash/<short-name>`** | Park unfinished commits you may need later | Author; delete when resumed or abandoned |

`main` and `prod` start equal (`6c64964`). They diverge once the next feature merges to `main` and you have **not** yet promoted.

---

## Feature workflow (normal)

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feature/short-name

# ... commit on this branch only ...

git push -u origin HEAD
# then open a PR: feature/short-name → main
```

Naming: `feature/git-branching-workflow`, `feature/k8s-watcher-docs`, `fix/webhook-hmac`. Keep one concern per branch.

**Agents / Cursor:** create the feature branch *before* the first commit of a task. Do not land on `main`.

---

## Stash (two different tools)

### 1. `git stash` — uncommitted local mess

Use when you must switch branches and have dirty files you are **not** ready to commit:

```bash
git stash push -u -m "wip: why"
git checkout main
# later:
git stash list
git stash pop
```

Do not stash secrets. Do not rely on stash as backup; it is local-only.

### 2. `stash/<name>` branch — unfinished *commits*

Use when work is committed but not PR-ready (blocked, context switch, share with a teammate):

```bash
git checkout -b stash/short-name
git push -u origin stash/short-name
```

When you resume:

```bash
git checkout main && git pull --ff-only
git checkout -b feature/short-name stash/short-name
# rebase or merge main, then PR feature → main
git push origin --delete stash/short-name   # after it is absorbed
```

Do **not** share a single immortal branch named `stash` that everyone force-pushes.

---

## Promote `main` → `prod`

Only after `main` is green and you want a partner/demo pin:

```bash
git checkout main
git pull --ff-only origin main
cd agent && pytest -q          # plus any sandbox checks you care about
git checkout prod
git merge --ff-only main
git push origin prod
```

If `--ff-only` fails, **stop**. Do not merge unrelated history into `prod`. Fix `main` first.

Optional: tag promotions (`v0.2.0`).

---

## Rules

1. Never commit on `prod`. Never `--force` push `main` or `prod`.
2. Never skip hooks (`--no-verify`) unless the user explicitly asks.
3. PRs: `feature/*` → `main` only. Not into `prod`.
4. Keep `prod` fast-forward from `main` (no extra commits on `prod`).
5. Delete `feature/*` and `stash/*` after merge.
6. GitHub: protect `main` and `prod` (require PR for `main`; disallow force-push on both). `gh` is optional; Settings → Branches works.

---

## First-time remote setup

If `origin` has only `main`:

```bash
git push -u origin prod
git push -u origin feature/git-branching-workflow
```

Then open a PR for the branching docs into `main`. After merge, `prod` can stay at the pre-docs SHA until you promote, or you promote once the PR lands — either is fine for this first cut.
