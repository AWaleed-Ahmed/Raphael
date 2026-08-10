# Raphael permission matrix (pilot)

Human-readable + machine-oriented summary of what Raphael may and may not do in a design-partner install.

**Principle:** production is read-only; durable changes enter only as **draft** GitHub PRs under human review. No auto-merge. No Secret payload reads.

---

## Summary

| Surface | Allowed | Denied |
|---------|---------|--------|
| GitHub | Read metadata; write agent branches; open **draft** PRs; optional labels/reviewers | Merge, admin, force-push to protected defaults, delete repos, read org secrets |
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
| Checks / commit status read | Optional | Optional |
| Request reviewers | Optional (`RAPHAEL_GITHUB_REVIEWERS`) | Optional |
| Merge / bypass branch protection | — | **Denied** |
| Admin / apps / secrets | — | **Denied** |

Env gates (code-enforced):

- `RAPHAEL_PARTNER_MODE=dry_run` → always dry-run placeholder URL
- `RAPHAEL_PARTNER_MODE=allowlist` + `RAPHAEL_PUBLISH_MODE=live` + class in `RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES` + token → draft PR
- Empty `RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES` → **no** live PRs

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
