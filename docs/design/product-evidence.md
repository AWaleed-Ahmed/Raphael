# Product evidence and claim boundaries

Research date: 2026-09-18. Basis: local source inspection, not a new deployment or end-to-end test run. “Implemented” means code is present; it does not establish production readiness, universal coverage, or a currently configured integration. The repository includes demo and fixture paths. Existing local untracked work was not used as proof of shipped capability.

## Product definition

Raphael is an evidence-led deployment repair agent for Kubernetes teams. Its implemented core coordinates failure intake, evidence, diagnosis, reproduction, source localization, constrained patching, validation, and reviewable delivery. Ignis is the separate sandbox executor. Raphael does not directly repair production. Self-healing is a product category whose actual scope here is **assisted repair preparation with human-controlled delivery**.

The landing page should let a visitor understand, within five seconds: a deployment fails; Raphael investigates and tests a proposed change elsewhere; the team reviews the result.

## Current, bounded by configuration

| Capability | Source inspected | Design consequence |
| --- | --- | --- |
| Graph with ingest → evidence → diagnose → reproduce → localize → patch → validate → publish/escalate; validation can retry patching within budget | `agent/raphael_agent/graph/graph.py`, `nodes.py` | Show an inspectable sequence and a bounded retry branch. Do not describe it as an unrestricted tool-using agent. The `build_stub_graph` name alone is not evidence that all nodes are fake: implementations contain both live and recorded modes. |
| Structured run state includes evidence, hypotheses/diagnosis, candidate patches, sandbox mode, results, budgets, and audit events | `agent/raphael_agent/graph/state.py` | A current “evidence dossier” is legitimate. The future generalized context builder is a different claim. |
| GitHub webhook intake and run API | `agent/raphael_agent/http_api/app.py` | GitHub Actions can be the primary trigger in the narrative. `/v1/runs`, run details and actions belong to the console, not a public marketing endpoint. |
| Kubernetes workload event normalization and webhook; watcher defaults off; demo file intake exists | `agent/raphael_agent/ingest/k8s_watcher.py` | Say “receives Kubernetes failure signals”; do not promise installation-free continuous discovery. A production watcher/forwarder is a separate dependency. |
| Alertmanager, Datadog, CloudWatch webhook handlers; APM evidence modules | `http_api/app.py`, `ingest/apm_webhook.py`, `evidence/apm.py` | Optional configured input paths, not proof of comprehensive turnkey integrations. Avoid a broad partner-logo wall. |
| GitHub/issue evidence adapters plus fixture fallback | `agent/raphael_agent/evidence/__init__.py`, `github_actions.py`, `issue.py`, `redaction.py` | Distinguish live, recorded, and illustrative evidence. The fallback is not a real incident. |
| Deterministic diagnosis, optional LLM diagnosis, model gateway | `diagnosis/analyzers.py`, `diagnosis/config.py`, `graph/nodes.py`, `model_gateway.py` | Deterministic-first investigation; LLM diagnosis defaults off. Do not show a live stream of invented AI thoughts. |
| Source localization and candidate ranking | `localization/`, `graph/nodes.py:node_localize` | Evidence can point to a repository file. Avoid suggesting perfect causal inference. |
| Narrow deterministic templates for probe port mismatch, bad image and missing config; optional model patching | `patch/templates.py`, `patch/llm.py`, `graph/nodes.py:node_patch` | Choose a readiness-probe port mismatch for the illustrative story. Do not use arbitrary application rewrites or broad infrastructure repair as proof. |
| Patch path allowlist, secret-pattern and privilege checks | `patch/config.py`, `patch/policy.py` | Show policy checks as a distinct gate. These are actual bounded checks, not a formal guarantee against every unsafe patch. |
| Six typed sandbox verbs with request/response schema validation | `sandbox_client/client.py`, `contracts/sandbox/` | Show a hard boundary; the agent does not get an arbitrary shell. Ignis owns execution. |
| Live and recorded reproduction/validation; failure-signature comparison, health checks, repeat runs and optional correctness signals | `graph/nodes.py:node_reproduce`, `node_validate`, `validation/signals.py` | Show before/after evidence and validation scope. Live graph currently includes a `deployment/payments-api` rollout target; do not claim arbitrary workload coverage. |
| Draft PR delivery with dry-run defaults and opt-in live publishing | `publish/config.py`, `publish/__init__.py`, `publish/github_client.py` | “Draft PR → human review” is the correct ordering. Dry-run preparation does not mean a real PR was opened. |
| Issue route produces a fix snippet, including a skipped-sandbox mode | `publish/__init__.py`, `graph/nodes.py` | Not every output is sandbox-validated or a PR. Keep the principal story explicitly scoped to the sandbox-backed draft-PR path. |
| Dispatch owns typed sequencing, leases, budgets and replay handling | `dispatch/raphael_dispatch/orchestrator.py`, `protocol.py` | Current infrastructure already has orchestration. Do not market the future harness as filling an entirely empty architecture. |
| Operator console with realistic mock runs, API support, retry/escalate/feedback | `frontend/src/main.js`, `frontend/README.md` | Existing frontend is a console, not a landing page. Its demo data is not customer proof; do not reuse fictional success metrics as testimonials. |

## In progress / incomplete

These are implementation gaps or documented follow-ups, not verified active assignments:

- The broader custom harness described in the attached brief has not been established by the inspected code. Current graph and dispatch are foundations, not the finished proposed mechanism.
- `Orchestrator.jobs` is process memory. `decision.md` D-20260829-01 records missing dispatch restart rehydration and manual lease reaping. Do not claim seamless recovery from every failure.
- `decision.md` D-20260830-01 records a `service_port_mismatch` signature/schema incompatibility at finalization. Its present status in the external Ignis executor was not retested here. Do not use that incident as the claimed successful demonstration.
- `docs/pilot-acceptance.md` calls Kubernetes intake deferred, while code now contains a gated webhook and normalization adapter. Resolve the distinction as “intake code exists; a shipped production watcher is not demonstrated.” Do not repeat stale deferred status as if no code exists.
- The older coding rules contain stale references to a local sandbox tree and “five verbs.” Current client, README and explicit verb list establish six verbs and the separate Ignis boundary.
- The source has recorded/fixture paths and the graph has no LangGraph checkpointer. A polished mockup must not imply that these modes are equivalent to verified live execution.
- Publishing guards check for a result ID and reject recorded validations when none passes, but the inspected publishing code does not establish an unconditional `full_validation == true` guarantee for every output. The site must not claim that every proposed change is fully validated. Scope all validation labels to their actual checks.

## Planned, from the supplied brief

A custom harness with structured context construction, selective evidence retrieval, tool selection and execution, observation-driven hypothesis revision, bounded iterations, failure recovery and human review. ReAct/DFSDT are candidate strategies, not settled architecture. Do not invent a tool registry API, exact storage technology, parallel agent count, context window size, completion date, or performance promise.

Existing structured state and bounded retries may be shown as current foundations. Only the separate **Planned architecture** panel may show the broader reason → select tool → execute → observe → update context loop. Dashed relationships and a persistent textual label identify this panel as planned.

## Safety and successful outcomes

Production access is read-only under the permission model. Sandbox actions use the typed executor boundary. Human review occurs on the draft PR; subsequent merge and deployment belong to the team's normal process. A green sandbox result is not a green production deployment.

A successful illustrative story ends at **Draft prepared · awaiting review**. A blocked story ends with a reason, evidence and next action. “Resolved,” “production healthy,” and “automatically deployed” are not valid synonyms for those outcomes.

## Source index

All paths above are relative to the repository root, two levels above this document. Further consulted sources: `README.md`, `design.md`, `CODING_RULE.md`, `docs/permission-matrix.md`, `docs/pilot-acceptance.md`, `decision.md`, `contracts/agent/`, and `frontend/package.json`.

Public references reviewed on 2026-09-18:

- [Revolte](https://revolte.ai/): live hero and agentic-loop section visually inspected. Borrow causal visibility and separation of execution from human control. Its current black/white/red identity, broad SDLC scope, product cards, numerical claims and wording are not Raphael's design.
- [Lazy](https://lazy.so/): text/DOM inspected; browser rendering remained incomplete during review. Concise action-led copy and staged product explanation were verifiable; detailed motion and final visual composition were not reliably evaluated.
- [Structured](https://structured.money/): retrieval returned a 502. No fresh visual claims are made. Existing `design.md` contains an earlier secondary-reference interpretation; it is background, not a newly verified observation.
