# Ingestion and diagnosis evidence: current implementation

**2026-09-27 update (branch pending review):** D-20260927-01 supersedes the
missing-boundary findings below. The bridge now forwards available run evidence
through internal `intake(initial_evidence=...)`; bounded redacted manifest
excerpts come from the ephemeral patch store. Three formerly blocked scenarios
passed real runs and are active. This does not add Actions-log downloading or
evidence collection to empty runs, nor change raw webhook persistence. The
following dated audit remains a historical baseline, not current branch status.

Verified 2026-09-26 against fetched `main` at `afa463d` and PR #27 follow-up
`111f42a`. This is a code audit, not a claim of live-provider verification.
The separate diagnosis-evidence-boundary work has not merged. In particular,
`Orchestrator.intake(initial_evidence=...)` does **not** exist in these revisions.

## 1. Trigger ingestion already exists

- `agent/raphael_agent/http_api/app.py:github_webhook` serves
  `POST /v1/webhooks/github`. `ingest/github.py:parse_github_webhook` verifies
  the signature when a webhook secret is configured, then delegates to
  `ingest/normalize.py`. Unsigned local/dev requests are allowed when no
  secret is configured; this is not unconditional production authentication.
- Normalizers support workflow failures/timeouts; check failures/timeouts/
  cancellations; deployment status failure/error; and open, labeled, or
  reopened Issues with the configured trigger label and a resolved SHA.
  The HTTP handler separately handles `issue_comment` commands (feature-gated)
  and `pull_request` feedback. These are not all new remediation triggers.
- `k8s_webhook`, `alertmanager_webhook`, `datadog_webhook`, and
  `cloudwatch_webhook` also exist, backed by `ingest/k8s_watcher.py` and
  `ingest/apm_webhook.py`. This does not establish live Kubernetes verification.
- `ingest/service.py:accept_normalized_event` fingerprints, applies tenant
  deduplication/cooldown/concurrency policy, records the decision, and persists
  the accepted run. `_try_dispatch_bridge` sends accepted work to the shared
  orchestrator when enabled; successful bridging prevents duplicate graph execution.
- `ingest/dispatch_bridge.py:build_job_envelope` transfers clone URL, SHA, and
  narrowed file path. `submit_to_dispatch` calls
  `orchestrator.intake(envelope, tenant_id=tenant_id)` and records the job-ID
  correlation. It does **not** pass collected evidence or the original trigger
  into the new dispatch state. This propagation gap is real; a second ingest
  implementation would not solve it.

## 2. Evidence collection already exists, with limits

`evidence/__init__.py:collect_evidence` selects existing APM evidence, Issue
evidence, GitHub event evidence, then fixture fallback. `graph/nodes.py:node_evidence`
uses that facade on the agent graph route. The connector dispatch route goes
directly from observation to diagnosis; it does not invoke this collection node.

- `evidence/github_actions.py:collect_github_actions_evidence` constructs
  repository/SHA/job correlation evidence and, when available, a 1,200-character
  stored-webhook excerpt. It does **not** download full Actions logs.
- `evidence/issue.py:collect_issue_evidence` redacts the body and bounds the
  assembled excerpt to 4,000 characters. Title/labels are not independently
  redacted there, and the marker is always true. Do not claim universal redaction.
- `evidence/apm.py` contains Prometheus/Datadog client code, metric analysis,
  and `APMEvidenceCollector.create_evidence_item`; its excerpt is capped at
  2,000 characters. Presence of adapter code is not proof of live credentials
  or blanket redaction; the facade returns existing APM evidence directly.
- `evidence/redaction.py:redact_evidence_item` copies an item and applies regex
  redaction to `summary` and `content_excerpt`: AWS access keys, Bearer tokens,
  key/secret/token/password assignments, and private-key blocks. It records
  match labels. It is neither recursive object sanitization nor comprehensive
  secret detection, and it preserves an already-supplied redaction marker.
- `dispatch/raphael_dispatch/orchestrator.py:_observation_evidence` serializes
  the observation result into a redacted summary (PR #26). `_after_observe`
  stores the signature/reproduction outcome and appends that item. Artifact
  IDs and any signature evidence references are metadata in this result;
  this path does not fetch their underlying logs/files. It does not impose a
  summary-size budget, and the separately stored signature is not redacted
  by the summary helper.
- PR #27 keeps deploy `rendered_files` patch-only and ephemeral; it does not
  turn them into source-linked diagnosis evidence. Its new durable projection
  strips patch bodies/diffs, not arbitrary strings throughout the run.

Additional boundary to track: `accept_normalized_event` calls
`RunStore.save_raw_event` before evidence processing. That method writes the
provided payload without redaction. PR #27's run-record protection does not
cover raw webhook files, logs, or historical records. No changes to those
paths are made by this audit.

## 3. Processing into diagnosis context is partial, not absent

Evidence items use `evidence_id`, `kind`, `summary`, optional `content_excerpt`,
source/provenance, and redaction metadata. On the dispatch route today,
diagnosis receives the narrowed-location context item plus the serialized
connector observation item, along with the run's failure signature. The original
ingest evidence and rendered source comments are not bridged into these items.

- `diagnosis/analyzers.py:_evidence_blob` concatenates all summaries/excerpts
  without a shared total-size cap. `_read_workspace_text` optionally reads
  locally accessible manifest files; its 200,000-character limit is checked
  after reading each whole file, so it is not a strict hard bound. A customer
  connector workspace path is not automatically a locally accessible core path.
- `diagnosis/__init__.py:diagnose` runs deterministic analyzers, constructs up
  to three hypotheses, applies confidence/block gates, optionally calls LLM
  refinement, and schema-validates the result. Existing Issue-specific behavior
  and optional model paths remain; this is not a new empty module.
- `diagnosis/llm.py:try_llm_diagnosis` has its own projection: first eight
  evidence items, each excerpt capped at 800 characters. Summaries are not
  capped by this projection, and it does not itself redact its inputs. This
  local model-input projection is not a shared safe-context boundary.

There is no merged, common source/trigger-to-diagnosis builder enforcing total
bounds, consistent real redaction, and provenance across both routes. That is
the precise integration work to complete on top of the existing modules.
PR #25's three blocked safety scenarios should remain blocked until this
boundary is implemented and their real runs pass. No replacement ingestion,
collection, or diagnosis subsystem is justified by these findings.
