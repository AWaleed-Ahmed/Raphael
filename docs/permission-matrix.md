# Raphael permission matrix (pilot)

Human-readable + machine-oriented summary of what Raphael may and may not do in a design-partner install.

**Principle:** production is read-only; durable changes enter only as **draft** GitHub PRs under human review. No auto-merge. No Secret payload reads.

---

## Summary

| Surface | Allowed | Denied |
|---------|---------|--------|
| GitHub | Read metadata; write agent branches; open **draft** PRs (Route A); comment fix snippets on Issues (Route B); optional labels/reviewers; optional **advisory** Checks | Merge, admin, force-push to protected defaults, delete repos, read org secrets, **required** Checks that gate merge |
| Production Kubernetes | get/list/watch allowlisted workloads/events/logs (bounded) | create/update/patch/delete; read Secret **data**; exec; port-forward to prod for mutation |
| Sandbox cluster | Via sandbox controller only (create/deploy/observe/validate/finalize/destroy) | Agent holding sandbox kubeconfig; free-form kubectl API |
| Agent host secrets | Env vars for webhook HMAC + GitHub token (operator-managed) | Committing tokens; logging plaintext secrets |
| Publish modes | `dry_run` (default partner); live draft only if allowlisted failure class | Live publish with empty allowlist; non-draft PRs |

---

## GitHub

| Capability | PAT / App | Pilot default |
|------------|-----------|---------------|
| `contents:read` | Required | On |
| `contents:write` (agent branches `raphael/*`) | Live publish only | Off until allowlist |
| `pull_requests:write` (draft=true) | Live publish only | Off until allowlist |
| `issues:write` — Route B fix-snippet comments | Live issue comments | Off until live issue comments |
| `issues:write` — `/raphael` **issue_comment replies** | `RAPHAEL_GITHUB_COMMANDS=1` + token | **Off** |
| `issues:write` / `pull_requests:write` — additive labels (`raphael:draft`, `raphael:needs-human`, `raphael:escalated`) | `RAPHAEL_GITHUB_AUTO_COMMENTS` (unset inherits commands) | **Off** — never strips `raphael:fix` |
| `issues:write` — sticky “Raphael actions” footer | Same auto-comment knob | **Off** — no Merge action in the footer |
| Checks write (`Raphael (advisory)`) | Opt-in `RAPHAEL_GITHUB_CHECK_RUNS=1` | **Off** — never a required merge check |
| Checks / commit status read | Optional | Optional |
| Request reviewers | Optional (`RAPHAEL_GITHUB_REVIEWERS`) | Optional |
| Merge / bypass branch protection | — | **Denied** |
| Administration / apps / secrets | — | **Denied** |
| Environments (write) / Workflows (write) | — | **Denied** (PRD §7.3) |

Aligned with [`interface/github-native/prd.md`](../interface/github-native/prd.md) §7.3. **Must not request:** Administration, Secrets, Environments (write), Workflows (write).

Env gates (code-enforced):

- `RAPHAEL_PARTNER_MODE=dry_run` → always dry-run placeholder URL
- `RAPHAEL_PARTNER_MODE=allowlist` + `RAPHAEL_PUBLISH_MODE=live` + class in `RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES` + token → draft PR
- Empty `RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES` → **no** live PRs
- Route B (`delivery_mode=issue_snippet`): posts an issue comment with a fix snippet; **never** opens a PR. Human opens the PR.
- `RAPHAEL_GITHUB_COMMANDS=0` (default) → do **not** parse `issue_comment` bodies
- `RAPHAEL_GITHUB_AUTO_COMMENTS` unset → same as `COMMANDS`; explicit `0`/`1` override. Gates terminal comments, additive labels, and the sticky footer
- `RAPHAEL_GITHUB_CHECK_RUNS=0` (default) → no Check API calls (does **not** inherit command/auto-comment flags)
- `RAPHAEL_GITHUB_CHECK_RUNS=1` + token → advisory Check `Raphael (advisory)` on `commit_sha`; conclusion **`neutral`** unless `RAPHAEL_GITHUB_CHECK_ADVISORY_SUCCESS=1` (happy terminals only). Never `failure`. Never required for merge.
- Issue trigger label: `RAPHAEL_ISSUE_TRIGGER_LABEL` (default `raphael:fix`)

---

## Kubernetes (customer / production evidence)

| API | Allowed | Denied |
|-----|---------|--------|
| Pods, Pod logs (bounded), Events | get/list/watch | delete, patch, exec |
| Deployments, ReplicaSets, Services | get/list/watch | scale, patch, delete |
| ConfigMaps | get (non-secret) | mutate |
| Secrets | **none** (no get that returns `data`) | all Secret payload access |
| Namespaces / cluster-scoped | only if explicitly allowlisted later | create cluster roles, PSA bypass |

Implement evidence adapters with a dedicated ServiceAccount that omits `secrets` get on payloads. Sandbox never copies production Secret values (synthetic fixtures only).

---

## Sandbox subsystem

| Actor | May | Must not |
|-------|-----|----------|
| Sandbox controller | Namespace-per-run isolation, deploy/observe/validate/finalize/destroy | Open GitHub PRs; talk to production API |
| Agent | Call typed HTTP verbs + health | Hold production write kubeconfig; raw shell to cluster |
| Operator | `POST /v1/admin/force-cleanup` on controller | Expect agent to cleanup remote clusters |

---

## Explicit deny list (checklist)

- [ ] No required GitHub Check that satisfies merge without human review  
- [ ] No merge / auto-merge / self-approve of Raphael PRs  
- [ ] No production create/update/patch/delete from Raphael  
- [ ] No Kubernetes Secret payload reads  
- [ ] No live GitHub publish when partner mode is `dry_run`  
- [ ] No live GitHub publish when failure-class allowlist is empty  
- [ ] No publishing without `result_id` + passing validation  
- [ ] No committing `.env` / tokens into the repo  

---

## Related

- Install: [`pilot-install.md`](pilot-install.md)  
- Acceptance: [`pilot-acceptance.md`](pilot-acceptance.md)  
- Pilot week: [`pilot-week-runbook.md`](pilot-week-runbook.md)  
- Coding rules §1 / §13: [`../CODING_RULE.md`](../CODING_RULE.md)  
- Guardrail tests: `agent/tests/test_guardrails.py`
- GitHub-native: [`../interface/github-native/prd.md`](../interface/github-native/prd.md) (`D-20260814-02` … `D-20260814-06`)
