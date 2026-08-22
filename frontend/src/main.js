import "./styles.css";

const API_BASE = (import.meta.env.VITE_RAPHAEL_API_URL || "").replace(/\/$/, "");
const INTERFACE_TOKEN = import.meta.env.VITE_RAPHAEL_INTERFACE_TOKEN || "";

const mockRuns = [
  {
    run_id: "run-kgroot-7f31",
    status: "failed_closed",
    repository: { owner: "acme-platform", name: "kgroot-test-app" },
    commit_sha: "efad08bdabbabf95322b5cf0caf54b26e0e9bb7a",
    created_at: "2026-08-17T08:02:00Z",
    updated_at: "2026-08-17T08:07:14Z",
    terminal_reason: "validation_failed",
    failure_class: "service_port_mismatch",
    trigger_kind: "github_workflow_run",
  },
  {
    run_id: "run-checkout-4a12",
    status: "success_draft_pr_ready",
    repository: { owner: "northstar", name: "checkout" },
    commit_sha: "a5d9c13b2e4f8a77",
    created_at: "2026-08-17T07:44:00Z",
    updated_at: "2026-08-17T07:51:40Z",
    terminal_reason: null,
    failure_class: "probe_misconfiguration",
    trigger_kind: "github_check_run",
    pull_request_url: "https://github.com/northstar/checkout/pull/184",
  },
  {
    run_id: "run-benchmark-91c8",
    status: "escalated",
    repository: { owner: "acme-platform", name: "benchmark-ai" },
    commit_sha: "c698d93541edbd5a455f7ae1fdee89a00c548921",
    created_at: "2026-08-17T06:18:00Z",
    updated_at: "2026-08-17T06:29:05Z",
    terminal_reason: "human_requested",
    failure_class: "invalid_missing_config",
    trigger_kind: "datadog_alert",
  },
  {
    run_id: "run-dashboard-2b8e",
    status: "running",
    repository: { owner: "volcano-sh", name: "dashboard" },
    commit_sha: "2d6be1818c1fedc2e621c6632e272fc066ae6e1d",
    created_at: "2026-08-17T05:56:00Z",
    updated_at: "2026-08-17T06:01:18Z",
    terminal_reason: null,
    failure_class: "latency_regression",
    trigger_kind: "prometheus_alert",
  },
  {
    run_id: "run-inventory-0c44",
    status: "success_fix_proposed",
    repository: { owner: "northstar", name: "inventory" },
    commit_sha: "8c340a1d90bb21ee",
    created_at: "2026-08-16T22:10:00Z",
    updated_at: "2026-08-16T22:21:32Z",
    terminal_reason: null,
    failure_class: "invalid_missing_config",
    trigger_kind: "cloudwatch_alarm",
  },
];

const mockDetails = {
  "run-kgroot-7f31": {
    ...mockRuns[0],
    diagnosis: {
      classification: { failure_class: "service_port_mismatch", confidence: 0.94 },
      selected_hypothesis_id: "hyp-01",
      summary: "payment-service targets port 8081 while its container listens on 8080.",
    },
    failure_signature: {
      key: "service_port_mismatch:payment-service:8081",
      class: "service_port_mismatch",
      confidence: 0.9,
      normalized: {
        reason: "TargetPortMismatch",
        resource_kind: "Service",
        resource_name: "payment-service",
        target_port: 8081,
        container_ports: [8080, 5432, 6379],
      },
    },
    evidence: [
      { kind: "k8s_event", title: "Connection refused", body: "service targetPort 8081 does not match container ports", source: "payment-service" },
      { kind: "pod_status", title: "Workload running", body: "payment-service-6c7c4d phase=Running", source: "k8s" },
      { kind: "manifest", title: "Deployment manifest", body: "kubernetes/payment-service.yaml: service.targetPort", source: "git" },
    ],
    candidate_patches: [{ path: "kubernetes/payment-service.yaml", line: 31, score: 0.91, mapping_methods: ["deployment_diff", "log_template"], candidate_type: "kubernetes_manifest" }],
    validation_results: [{ passed: false, full_validation: false, before_signature_key: "service_port_mismatch:payment-service:8081", after_signature_key: "service_port_mismatch:payment-service:8081", checks: [{ name: "signature_compare", status: "failed", message: "Failure signature remained after the candidate run." }] }],
    model_results: {
      failure_classifier: { failure_class: "service_port_mismatch", confidence: 0.742042, rule_based: true },
      incident_similarity: { results: [{ incident_id: "incident-1744", similarity: 0.266545, successful_fix_template: "align_container_port" }] },
      trace_anomaly: { is_anomaly: true, anomaly_probability: 0.993241, rule_evidence: "explicit_error_span_or_status" },
      patch_selector: { policy_allowed: true, safe_template: "fix_service_target_port", requires_sandbox_validation: true },
    },
    audit_events: [
      { at: "08:02:02", stage: "ingest", detail: "fingerprint created" },
      { at: "08:03:11", stage: "localize", detail: "1 source candidate ranked" },
      { at: "08:05:56", stage: "validate", detail: "signature_compare failed" },
    ],
  },
  "run-checkout-4a12": {
    ...mockRuns[1],
    diagnosis: { classification: { failure_class: "probe_misconfiguration", confidence: 0.91 }, summary: "The readiness probe path changed without a matching application route." },
    failure_signature: { key: "probe_404_path:checkout-api:/ready", class: "probe_misconfiguration", confidence: 0.95, normalized: { reason: "ReadinessProbeHTTPError", resource_name: "checkout-api" } },
    evidence: [{ kind: "stack_trace", title: "Probe returned 404", body: "GET /ready → 404 from checkout-api", source: "k8s event" }, { kind: "git_diff", title: "Changed hunk", body: "deploy/deployment.yaml: readinessProbe.httpGet.path", source: "git" }],
    candidate_patches: [{ path: "deploy/deployment.yaml", line: 42, score: 0.96, mapping_methods: ["deployment_diff", "trace_divergence"], candidate_type: "kubernetes_manifest" }],
    validation_results: [{ passed: true, full_validation: false, before_signature_key: "probe_404_path:checkout-api:/ready", after_signature_key: "healthy", checks: [{ name: "signature_compare", status: "passed", message: "Signature cleared." }, { name: "repeatability", status: "passed", message: "3/3 repeat runs passed." }] }],
    model_results: { failure_classifier: { failure_class: "probe_misconfiguration", confidence: 0.96, rule_based: true }, trace_anomaly: { is_anomaly: true, anomaly_probability: 0.998, rule_evidence: "error_status_vs_healthy_baseline" }, patch_selector: { policy_allowed: true, safe_template: "fix_probe_port_mismatch", requires_sandbox_validation: true } },
    audit_events: [{ at: "07:44:02", stage: "ingest", detail: "GitHub check failure accepted" }, { at: "07:49:18", stage: "sandbox", detail: "bad signature reproduced" }, { at: "07:51:40", stage: "publish", detail: "draft PR opened" }],
  },
  "run-benchmark-91c8": {
    ...mockRuns[2],
    diagnosis: { classification: { failure_class: "invalid_missing_config", confidence: 0.96 }, summary: "executor references availability_zones, which is missing from outputs-infrastructure." },
    failure_signature: { key: "missing_configmap_key:outputs-infrastructure:availability_zones", class: "invalid_missing_config", confidence: 0.95, normalized: { reason: "CreateContainerConfigError", resource_name: "executor" } },
    evidence: [{ kind: "k8s_event", title: "CreateContainerConfigError", body: "configmap key not found: availability_zones", source: "executor" }, { kind: "manifest", title: "ConfigMap reference", body: "executor/deploy/base/config.yml", source: "git" }],
    candidate_patches: [{ path: "executor/deploy/base/config.yml", line: 19, score: 0.88, mapping_methods: ["stack_trace", "deployment_diff"], candidate_type: "kubernetes_manifest" }],
    validation_results: [],
    model_results: { failure_classifier: { failure_class: "invalid_missing_config", confidence: 0.747914, rule_based: true }, incident_similarity: { results: [{ incident_id: "incident-0579", similarity: 0.545231, successful_fix_template: "revert_configmap_entry" }] }, trace_anomaly: { is_anomaly: true, anomaly_probability: 0.993241, rule_evidence: "explicit_error_span_or_status" }, patch_selector: { policy_allowed: true, safe_template: "restore_configmap_key", requires_sandbox_validation: true } },
    audit_events: [{ at: "06:18:02", stage: "ingest", detail: "Datadog alert normalized" }, { at: "06:24:10", stage: "diagnose", detail: "human review requested" }, { at: "06:29:05", stage: "escalate", detail: "patch publication stopped" }],
  },
  "run-dashboard-2b8e": {
    ...mockRuns[3],
    diagnosis: { classification: { failure_class: "latency_regression", confidence: 0.82 }, summary: "p95 latency is diverging from the healthy trace baseline." },
    failure_signature: { key: "trace_divergence:volcano-dashboard:list", class: "trace_divergence", confidence: 0.84, normalized: { reason: "LatencySLOBreach", resource_name: "volcano-dashboard" } },
    evidence: [{ kind: "trace", title: "First divergent span", body: "dashboard.query p95 812ms vs baseline 244ms", source: "OpenTelemetry" }, { kind: "metric", title: "SLO breach", body: "checkout_latency_p95 > 500ms for 8 minutes", source: "Prometheus" }],
    candidate_patches: [], validation_results: [], model_results: { trace_anomaly: { is_anomaly: true, anomaly_probability: 0.91, rule_evidence: "latency_vs_healthy_baseline" }, failure_classifier: { failure_class: "latency_regression", confidence: 0.82, rule_based: false } }, audit_events: [{ at: "05:56:02", stage: "ingest", detail: "Prometheus alert accepted" }, { at: "06:01:18", stage: "evidence", detail: "healthy trace comparison in progress" }],
  },
  "run-inventory-0c44": {
    ...mockRuns[4],
    diagnosis: { classification: { failure_class: "invalid_missing_config", confidence: 0.9 }, summary: "The inventory worker references a removed secret key." },
    failure_signature: { key: "missing_secret_key:inventory-db:password", class: "invalid_missing_config", confidence: 0.92, normalized: { reason: "SecretKeyNotFound", resource_name: "inventory-worker" } },
    evidence: [{ kind: "k8s_event", title: "Secret key missing", body: "secret inventory-db does not contain password", source: "k8s" }, { kind: "git_diff", title: "Changed deployment", body: "deploy/inventory-worker.yaml", source: "git" }],
    candidate_patches: [{ path: "deploy/inventory-worker.yaml", line: 56, score: 0.93, mapping_methods: ["deployment_diff", "log_template"], candidate_type: "kubernetes_manifest" }], validation_results: [{ passed: true, full_validation: true, before_signature_key: "missing_secret_key:inventory-db:password", after_signature_key: "healthy", checks: [{ name: "repeatability", status: "passed", message: "3/3 repeat runs passed." }] }], model_results: { failure_classifier: { failure_class: "invalid_missing_config", confidence: 0.9, rule_based: true }, patch_selector: { policy_allowed: true, safe_template: "restore_configmap_key", requires_sandbox_validation: true } }, audit_events: [{ at: "22:10:02", stage: "ingest", detail: "CloudWatch alarm normalized" }, { at: "22:18:12", stage: "validate", detail: "3 repeat runs passed" }, { at: "22:21:32", stage: "publish", detail: "issue fix snippet ready" }],
  },
};

const state = {
  runs: [...mockRuns],
  selectedRunId: "run-kgroot-7f31",
  filter: "all",
  query: "",
  loading: false,
  demoMode: !API_BASE,
  toast: null,
};

function icon(name) {
  const paths = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    activity: '<polyline points="3 12 7 12 10 4 14 20 17 12 21 12"/>',
    layers: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/>',
    plug: '<path d="M9 7V3m6 4V3M6 7h12v4a6 6 0 0 1-12 0V7Zm6 10v4"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.4 1.4-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-2v-.2a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L9 17l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H7v-2h.2a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L8.4 9 9.8 7.6l.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6V6h2v.2a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.2 9l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v2h-.2a1.7 1.7 0 0 0-1.6 1Z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.8-4L3 10m0-4v4h4M4 13a8 8 0 0 0 14.8 4L21 14m0 4v-4h-4"/>',
    arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    alert: '<path d="M10.3 3.8 2.2 18a2 2 0 0 0 1.7 3h16.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0ZM12 9v4m0 4h.01"/>',
    search: '<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/>',
    more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    external: '<path d="M14 3h7v7M21 3l-9 9"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.grid}</svg>`;
}

function esc(value) {
  return String(value ?? "").replace(/[&<>\"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}

function formatDate(value) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function relativeDate(value) {
  const mins = Math.max(1, Math.round((Date.now() - new Date(value).getTime()) / 60000));
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / 1440)}d ago`;
}

function label(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (m) => m.toUpperCase());
}

function statusTone(status) {
  if (status?.startsWith("success")) return "success";
  if (status === "running" || status === "pending") return "running";
  if (status === "escalated") return "warning";
  if (status === "failed_closed") return "danger";
  return "muted";
}

function statusBadge(status) {
  return `<span class="status-badge ${statusTone(status)}"><span class="status-dot"></span>${esc(label(status))}</span>`;
}

function initials(repo) {
  return (repo?.name || "R").slice(0, 2).toUpperCase();
}

function filteredRuns() {
  return state.runs.filter((run) => {
    const matchesFilter = state.filter === "all" || (state.filter === "active" ? ["running", "pending"].includes(run.status) : state.filter === "attention" ? ["failed_closed", "escalated"].includes(run.status) : run.status.startsWith("success"));
    const haystack = `${run.run_id} ${run.repository.owner}/${run.repository.name} ${run.failure_class || ""}`.toLowerCase();
    return matchesFilter && (!state.query || haystack.includes(state.query.toLowerCase()));
  });
}

function metrics() {
  return {
    active: state.runs.filter((r) => ["running", "pending"].includes(r.status)).length,
    recovered: state.runs.filter((r) => r.status.startsWith("success")).length,
    attention: state.runs.filter((r) => ["failed_closed", "escalated"].includes(r.status)).length,
    reliability: "99.2%",
  };
}

function render() {
  const selected = mockDetails[state.selectedRunId] || state.runs.find((run) => run.run_id === state.selectedRunId) || mockDetails[mockRuns[0].run_id];
  const m = metrics();
  const runs = filteredRuns();
  document.querySelector("#app").innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand"><div class="brand-mark">R</div><div><strong>raphael</strong><span>deployment intelligence</span></div></div>
        <div class="workspace-switcher"><div class="workspace-avatar">A</div><div><small>Workspace</small><strong>Acme Platform</strong></div><span class="chevron">⌄</span></div>
        <nav class="nav"><div class="nav-label">Workspace</div>${navItem("Overview", "grid", true)}${navItem("Incidents", "activity", false, `${m.attention}`)}${navItem("Deployments", "layers")}${navItem("Integrations", "plug")}<div class="nav-label nav-label-lower">Manage</div>${navItem("Settings", "settings")}</nav>
        <div class="sidebar-footer"><div class="plan-card"><div class="plan-top"><span>TRIAL</span><span>7 days left</span></div><div class="plan-title">4 / 10 remediations</div><div class="progress"><span style="width:40%"></span></div><button class="text-button">View usage ${icon("arrow")}</button></div><div class="user-row"><div class="user-avatar">AW</div><div><strong>Alex Waleed</strong><span>Administrator</span></div><span class="chevron">⌄</span></div></div>
      </aside>
      <main class="main-content">
        <header class="topbar"><div class="breadcrumbs"><span>Workspace</span><b>/</b><strong>Overview</strong></div><div class="topbar-actions"><div class="connection-pill"><span></span>${state.demoMode ? "Demo data" : "Agent connected"}</div><button class="icon-button" title="Refresh" data-action="refresh">${icon("refresh")}</button><div class="topbar-avatar">AW</div></div></header>
        <section class="page-content">
          <div class="welcome-row"><div><p class="eyebrow">MONDAY, AUGUST 17, 2026</p><h1>Good morning, Alex <span>✦</span></h1><p class="lede">Here’s what Raphael is watching across your deployments.</p></div><button class="primary-button" data-action="new-run">${icon("plus")} Start diagnostic</button></div>
          ${state.demoMode ? `<div class="demo-banner"><div class="demo-icon">✦</div><div><strong>You're exploring demo data</strong><span>Connect your Raphael agent to see live incidents, evidence, and validated fixes.</span></div><button class="banner-action" data-action="connect">Connect agent ${icon("arrow")}</button></div>` : ""}
          <div class="metric-grid"><div class="metric-card"><div class="metric-label">Active runs <span class="metric-icon blue">${icon("activity")}</span></div><div class="metric-value">${m.active}</div><div class="metric-foot"><span class="trend neutral">● monitoring</span><span>right now</span></div></div><div class="metric-card"><div class="metric-label">Fixes validated <span class="metric-icon green">${icon("check")}</span></div><div class="metric-value">${m.recovered}</div><div class="metric-foot"><span class="trend up">↑ 18%</span><span>vs last week</span></div></div><div class="metric-card"><div class="metric-label">Needs attention <span class="metric-icon orange">${icon("alert")}</span></div><div class="metric-value">${m.attention}</div><div class="metric-foot"><span class="trend down">↓ 2</span><span>vs last week</span></div></div><div class="metric-card accent-card"><div class="metric-label">Reliability score <span class="metric-icon violet">${icon("activity")}</span></div><div class="metric-value">${m.reliability}</div><div class="metric-foot"><span class="trend up">↑ 0.8%</span><span>last 30 days</span></div></div></div>
          <div class="section-heading"><div><h2>Recent runs</h2><p>Every signal, hypothesis, and sandbox result in one place.</p></div><button class="outline-button" data-action="view-all">View all ${icon("arrow")}</button></div>
          <div class="content-grid"><section class="runs-card"><div class="runs-toolbar"><div class="filter-tabs">${filterTab("all", "All runs", state.runs.length)}${filterTab("active", "Active", m.active)}${filterTab("attention", "Attention", m.attention)}${filterTab("recovered", "Recovered", m.recovered)}</div><label class="search-box">${icon("search")}<input id="run-search" placeholder="Search runs" value="${esc(state.query)}"/></label></div><div class="run-list">${runs.length ? runs.map(runRow).join("") : `<div class="empty-state"><div>${icon("search")}</div><strong>No matching runs</strong><span>Try a different search or filter.</span></div>`}</div><div class="table-footer"><span>Showing ${runs.length} of ${state.runs.length} runs</span><button class="pagination-button">1</button><button class="pagination-button muted-page">2</button><button class="pagination-button muted-page">${icon("arrow")}</button></div></section><aside class="detail-card">${detailPanel(selected)}</aside></div>
        </section>
      </main>
    </div>
    ${state.toast ? `<div class="toast ${state.toast.kind}"><span>${state.toast.kind === "success" ? icon("check") : icon("alert")}</span>${esc(state.toast.message)}</div>` : ""}
    <div id="modal-root"></div>
  `;
  bindEvents();
}

function navItem(text, iconName, active = false, count = "") { return `<button class="nav-item ${active ? "active" : ""}">${icon(iconName)}<span>${text}</span>${count ? `<em>${count}</em>` : ""}</button>`; }
function filterTab(value, text, count) { return `<button class="filter-tab ${state.filter === value ? "active" : ""}" data-filter="${value}">${text}<span>${count}</span></button>`; }

function runRow(run) {
  const selected = state.selectedRunId === run.run_id;
  return `<button class="run-row ${selected ? "selected" : ""}" data-run-id="${esc(run.run_id)}"><div class="repo-avatar ${statusTone(run.status)}">${initials(run.repository)}</div><div class="run-main"><div class="run-title"><strong>${esc(run.repository.owner)}/${esc(run.repository.name)}</strong>${statusBadge(run.status)}</div><div class="run-meta"><span>${esc(run.failure_class ? label(run.failure_class) : "No failure detected")}</span><span class="dot-separator">·</span><span>${relativeDate(run.updated_at)}</span></div></div><div class="run-trigger">${esc(label(run.trigger_kind))}</div><div class="row-arrow">${icon("arrow")}</div></button>`;
}

function detailPanel(run) {
  if (!run) return `<div class="detail-empty">Select a run to inspect its evidence.</div>`;
  const diagnosis = run.diagnosis || {};
  const classification = diagnosis.classification || {};
  const signature = run.failure_signature || {};
  const validation = (run.validation_results || [])[run.validation_results?.length - 1];
  return `<div class="detail-header"><div><p class="eyebrow">RUN DETAIL</p><h2>${esc(run.repository.owner)}/${esc(run.repository.name)}</h2><p class="detail-id">${esc(run.run_id)} <span>·</span> ${esc(run.commit_sha.slice(0, 12))}</p></div><button class="icon-button">${icon("more")}</button></div><div class="detail-actions">${run.status === "running" ? `<button class="outline-button small" data-action="escalate" data-run="${run.run_id}">Escalate</button>` : `<button class="outline-button small" data-action="retry" data-run="${run.run_id}">${icon("refresh")} Retry</button>`}<button class="primary-button small" data-action="feedback" data-run="${run.run_id}">Give feedback</button></div><div class="detail-status-row"><div>${statusBadge(run.status)}</div><span>Updated ${formatDate(run.updated_at)}</span></div><div class="detail-section"><div class="detail-section-title"><span class="number-badge">01</span><div><h3>Diagnosis</h3><p>What Raphael thinks happened</p></div></div><div class="diagnosis-box"><div class="diagnosis-top"><strong>${esc(label(classification.failure_class || run.failure_class || "Pending diagnosis"))}</strong><span class="confidence">${classification.confidence ? `${Math.round(classification.confidence * 100)}% confidence` : "Analyzing"}</span></div><p>${esc(diagnosis.summary || "The agent is collecting evidence from the deployment and its healthy baseline.")}</p></div></div><div class="detail-section"><div class="detail-section-title"><span class="number-badge">02</span><div><h3>Failure fingerprint</h3><p>Stable signal used for comparison</p></div></div><div class="fingerprint-box"><code>${esc(signature.key || "Awaiting observation")}</code>${signature.normalized ? `<div class="fingerprint-grid"><span>Reason<strong>${esc(signature.normalized.reason || "—")}</strong></span><span>Resource<strong>${esc(signature.normalized.resource_name || "—")}</strong></span><span>Confidence<strong>${signature.confidence ? `${Math.round(signature.confidence * 100)}%` : "—"}</strong></span></div>` : ""}</div></div><div class="detail-section"><div class="detail-section-title"><span class="number-badge">03</span><div><h3>Evidence collected</h3><p>${(run.evidence || []).length} redacted signals with provenance</p></div><button class="link-button">View all ${icon("arrow")}</button></div><div class="evidence-list">${(run.evidence || []).slice(0, 3).map((item) => `<div class="evidence-item"><div class="evidence-icon ${item.kind === "k8s_event" ? "orange" : item.kind === "trace" ? "blue" : "purple"}">${icon(item.kind === "trace" ? "activity" : item.kind === "k8s_event" ? "alert" : "layers")}</div><div><strong>${esc(item.title)}</strong><p>${esc(item.body)}</p><span>${esc(item.source)}</span></div></div>`).join("") || `<div class="muted-copy">Evidence will appear after ingestion completes.</div>`}</div></div><div class="detail-section"><div class="detail-section-title"><span class="number-badge">04</span><div><h3>Sandbox validation</h3><p>Counterfactual proof before delivery</p></div></div>${validation ? `<div class="validation-row ${validation.passed ? "passed" : "failed"}"><span>${icon(validation.passed ? "check" : "alert")}</span><div><strong>${validation.passed ? "Fix validated" : "Validation blocked"}</strong><p>${esc(validation.checks?.[0]?.message || (validation.passed ? "Signature cleared and repeatability checks passed." : "The original failure signature remained."))}</p></div></div>` : `<div class="validation-pending"><span class="pulse"></span><div><strong>Validation in progress</strong><p>Waiting for sandbox evidence and repeatability checks.</p></div></div>`}</div>${deliveryBlock(run)}<div class="detail-footer"><span>Created ${formatDate(run.created_at)}</span><button class="link-button">Open audit log ${icon("arrow")}</button></div>`;
}

function deliveryBlock(run) {
  const pr = run.pull_request_url;
  const patches = run.candidate_patches || [];
  if (!pr && !patches.length) return "";
  return `<div class="detail-section delivery-section"><div class="detail-section-title"><span class="number-badge">05</span><div><h3>Delivery</h3><p>${pr ? "Draft pull request ready for review" : "Candidate patch under review"}</p></div></div><div class="delivery-row"><div class="delivery-icon">${icon(pr ? "external" : "layers")}</div><div><strong>${pr ? "Draft PR opened" : `${patches.length} candidate patch${patches.length > 1 ? "es" : ""}`}</strong><p>${pr ? "Review the evidence matrix and rollback steps in GitHub." : `${esc(patches[0]?.path || "source candidate")} · score ${Math.round((patches[0]?.score || 0) * 100)}%`}</p></div>${pr ? `<a class="outline-button small" href="${esc(pr)}" target="_blank" rel="noreferrer">Open PR ${icon("arrow")}</a>` : ""}</div></div>`;
}

function bindEvents() {
  document.querySelectorAll("[data-run-id]").forEach((el) => el.addEventListener("click", () => { state.selectedRunId = el.dataset.runId; render(); }));
  document.querySelectorAll("[data-filter]").forEach((el) => el.addEventListener("click", () => { state.filter = el.dataset.filter; render(); }));
  const search = document.querySelector("#run-search");
  if (search) search.addEventListener("input", (event) => { state.query = event.target.value; render(); const input = document.querySelector("#run-search"); input?.focus(); input?.setSelectionRange(state.query.length, state.query.length); });
  document.querySelectorAll("[data-action]").forEach((el) => el.addEventListener("click", () => handleAction(el.dataset.action, el.dataset.run)));
}

async function handleAction(action, runId) {
  if (action === "refresh") return loadRuns();
  if (action === "new-run" || action === "connect") return openCreateModal();
  if (action === "view-all") { state.filter = "all"; state.query = ""; render(); return; }
  if (!runId) return;
  if (action === "feedback") return openFeedbackModal(runId);
  const verb = action === "retry" ? "retry" : "escalate";
  try {
    await apiAction(runId, verb);
    state.toast = { kind: "success", message: `${label(verb)} requested for ${runId}` };
    await loadRuns(false);
  } catch (error) { state.toast = { kind: "error", message: error.message || "Action could not be completed" }; render(); }
}

function openFeedbackModal(runId) {
  document.querySelector("#modal-root").innerHTML = `<div class="modal-backdrop"><div class="modal"><button class="modal-close" data-close>×</button><p class="eyebrow">RUN FEEDBACK</p><h2>How did this remediation land?</h2><p class="modal-copy">Your feedback becomes part of Raphael’s audit trail and learning set.</p><div class="feedback-options"><button data-feedback="accepted">✓ Accepted</button><button data-feedback="edited">↗ Edited</button><button data-feedback="rejected">× Rejected</button></div><textarea id="feedback-notes" placeholder="Optional notes for your team"></textarea><button class="primary-button full" data-submit-feedback="${runId}">Save feedback</button></div></div>`;
  document.querySelector("[data-close]")?.addEventListener("click", closeModal);
  document.querySelectorAll("[data-feedback]").forEach((button) => button.addEventListener("click", () => { document.querySelectorAll("[data-feedback]").forEach((b) => b.classList.remove("selected")); button.classList.add("selected"); button.dataset.selected = "true"; }));
  document.querySelector("[data-submit-feedback]")?.addEventListener("click", async (event) => { const chosen = document.querySelector("[data-feedback].selected")?.dataset.feedback; if (!chosen) return; try { await apiAction(event.target.dataset.submitFeedback, "feedback", chosen, document.querySelector("#feedback-notes")?.value); state.toast = { kind: "success", message: "Feedback recorded" }; closeModal(); render(); } catch (error) { state.toast = { kind: "error", message: error.message }; render(); } });
}

function openCreateModal() {
  document.querySelector("#modal-root").innerHTML = `<div class="modal-backdrop"><div class="modal"><button class="modal-close" data-close>×</button><p class="eyebrow">MANUAL DIAGNOSTIC</p><h2>Start a safe diagnostic</h2><p class="modal-copy">Create a run from a pinned commit. Raphael will apply the same partner and sandbox gates as webhook-triggered runs.</p><label>Repository<input id="new-repo" value="acme-platform/checkout" /></label><label>Commit SHA<input id="new-sha" value="a5d9c13b2e4f8a77" /></label><label>Environment<select id="new-env"><option>staging</option><option>preview</option><option>production (observe only)</option></select></label><button class="primary-button full" data-submit-run>Start diagnostic ${icon("arrow")}</button></div></div>`;
  document.querySelector("[data-close]")?.addEventListener("click", closeModal);
  document.querySelector("[data-submit-run]")?.addEventListener("click", submitCreate);
}

async function submitCreate() {
  const [owner, name] = document.querySelector("#new-repo").value.trim().split("/");
  if (!owner || !name) return;
  try { const result = await apiCreate({ trigger_kind: "manual_ui", action_id: crypto.randomUUID(), repository: { owner, name }, commit_sha: document.querySelector("#new-sha").value.trim(), target_environment: document.querySelector("#new-env").value }); state.toast = { kind: "success", message: `Diagnostic ${result.run_id || "created"}` }; closeModal(); await loadRuns(false); } catch (error) { state.toast = { kind: "error", message: error.message }; render(); }
}

function closeModal() { document.querySelector("#modal-root").innerHTML = ""; }

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (INTERFACE_TOKEN) headers.Authorization = `Bearer ${INTERFACE_TOKEN}`;
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload?.error?.message || payload?.message || `Request failed (${response.status})`);
  return payload;
}

async function loadRuns(showLoading = true) {
  if (showLoading) { state.loading = true; render(); }
  if (!API_BASE) { state.loading = false; state.toast = { kind: "success", message: "Demo data refreshed" }; render(); return; }
  try { const payload = await request("/v1/runs?limit=100"); state.runs = payload.runs || []; state.demoMode = false; state.toast = { kind: "success", message: "Runs refreshed" }; } catch (error) { state.demoMode = true; state.toast = { kind: "error", message: "Agent unavailable — showing demo data" }; } finally { state.loading = false; render(); }
}

async function apiAction(runId, verb, outcome, notes) {
  if (!API_BASE) { const run = state.runs.find((item) => item.run_id === runId); if (run && verb === "escalate") run.status = "escalated"; if (run && verb === "retry") run.status = "running"; return { run_id: runId, status: run?.status }; }
  return request(`/v1/runs/${encodeURIComponent(runId)}/actions`, { method: "POST", body: JSON.stringify({ verb, action_id: crypto.randomUUID(), ...(outcome ? { outcome } : {}), ...(notes ? { notes } : {}) }) });
}

async function apiCreate(body) {
  if (!API_BASE) { const run = { run_id: `run-manual-${Math.random().toString(16).slice(2, 8)}`, status: "pending", repository: body.repository, commit_sha: body.commit_sha, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), failure_class: null, trigger_kind: body.trigger_kind }; state.runs.unshift(run); mockDetails[run.run_id] = { ...run, diagnosis: {}, evidence: [], audit_events: [] }; state.selectedRunId = run.run_id; return run; }
  return request("/v1/runs", { method: "POST", body: JSON.stringify(body) });
}

window.addEventListener("keydown", (event) => { if (event.key === "Escape") closeModal(); });
render();
