/** Interactive Raphael sidebar (webview) — How to Use, Runs, Actions. */

import * as vscode from "vscode";
import type { RunSummary } from "./agentClient";

export type PanelState = {
  connected: boolean;
  statusText: string;
  agentBaseUrl: string;
  runs: RunSummary[];
  selectedRunId?: string;
  error?: string | null;
};

export type PanelMessage =
  | { type: "ready" }
  | { type: "tab"; tab: "guide" | "runs" | "actions" }
  | { type: "refresh" }
  | { type: "testConnection" }
  | { type: "selectRun"; runId: string }
  | { type: "openRun"; runId: string }
  | { type: "applyFix"; runId: string }
  | { type: "openDraftPr"; runId: string }
  | { type: "feedbackAccepted"; runId: string }
  | { type: "feedbackRejected"; runId: string }
  | { type: "setApiToken" };

type HostHandlers = {
  onMessage: (msg: PanelMessage) => void | Promise<void>;
};

export class RaphaelPanelProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "raphael.panel";

  private view?: vscode.WebviewView;
  private state: PanelState = {
    connected: false,
    statusText: "Checking…",
    agentBaseUrl: "http://127.0.0.1:8091",
    runs: [],
    error: null,
  };
  private handlers?: HostHandlers;

  constructor(private readonly extensionUri: vscode.Uri) {}

  setHandlers(handlers: HostHandlers): void {
    this.handlers = handlers;
  }

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): void {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(this.extensionUri, "media")],
    };
    webviewView.webview.html = this.html(webviewView.webview);
    webviewView.webview.onDidReceiveMessage((raw) => {
      const msg = raw as PanelMessage;
      if (!msg || typeof msg !== "object" || !("type" in msg)) return;
      void this.handlers?.onMessage(msg);
    });
    this.postState();
  }

  update(partial: Partial<PanelState>): void {
    this.state = { ...this.state, ...partial };
    this.postState();
  }

  getState(): PanelState {
    return this.state;
  }

  private postState(): void {
    void this.view?.webview.postMessage({ type: "state", state: this.state });
  }

  private html(webview: vscode.Webview): string {
    const cssUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, "media", "panel.css")
    );
    const iconUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, "media", "icon.svg")
    );
    const nonce = getNonce();
    const csp = [
      `default-src 'none'`,
      `style-src ${webview.cspSource}`,
      `img-src ${webview.cspSource} data:`,
      `script-src 'nonce-${nonce}'`,
    ].join("; ");

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="${csp}" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <link rel="stylesheet" href="${cssUri}" />
  <title>Raphael</title>
</head>
<body>
  <div class="wrap">
    <header class="brand">
      <img class="brand-mark" src="${iconUri}" alt="" />
      <div class="brand-text">
        <h1>Raphael</h1>
        <p>Self-healing deploy agent</p>
      </div>
    </header>

    <div class="status-row">
      <span id="dot" class="dot" aria-hidden="true"></span>
      <span id="status" class="status-label">Checking…</span>
      <button class="icon-btn" id="btnRefresh" title="Refresh" aria-label="Refresh">↻</button>
    </div>

    <nav class="tabs" role="tablist">
      <button class="tab active" data-tab="guide" role="tab" aria-selected="true">How to use</button>
      <button class="tab" data-tab="runs" role="tab" aria-selected="false">Runs</button>
      <button class="tab" data-tab="actions" role="tab" aria-selected="false">Actions</button>
    </nav>

    <section id="panel-guide" class="panel active" role="tabpanel">
      <div class="guide">
        <article class="guide-card">
          <h3>1. Start the agent</h3>
          <p>In a terminal, from the Raphael <code>agent/</code> folder, run <code>raphael-agent-serve</code> on <code>127.0.0.1:8091</code>.</p>
        </article>
        <article class="guide-card">
          <h3>2. Open your app workspace</h3>
          <p>File → Open Folder on the repo that contains manifests (demo: <code>probe_port_mismatch</code>).</p>
        </article>
        <article class="guide-card">
          <h3>3. Connect &amp; pick a run</h3>
          <ol>
            <li>Open the <strong>Runs</strong> tab → refresh if needed.</li>
            <li>Click a run to select it.</li>
            <li>Open the <strong>Actions</strong> tab for Apply Fix, Draft PR, and Feedback.</li>
          </ol>
        </article>
        <article class="guide-card">
          <h3>Safety</h3>
          <p>Apply Fix only writes under allowlisted paths (e.g. <code>deploy/</code>). There is no Merge from the IDE.</p>
        </article>
        <button class="btn btn-secondary block" id="btnConnect">Test connection</button>
        <button class="btn btn-ghost block" id="btnToken">Set API token…</button>
      </div>
    </section>

    <section id="panel-runs" class="panel" role="tabpanel">
      <div class="toolbar">
        <button class="btn btn-primary block" id="btnRefreshRuns">Refresh runs</button>
      </div>
      <p class="section-title">Recent runs</p>
      <div id="runs" class="runs"></div>
    </section>

    <section id="panel-actions" class="panel" role="tabpanel">
      <div id="selected" class="selected-box">
        <h2>No run selected</h2>
        <p class="meta">Choose a run in the Runs tab first.</p>
      </div>
      <div class="actions">
        <button class="btn btn-primary block" data-action="openRun" disabled>Open run details</button>
        <button class="btn btn-secondary block" data-action="applyFix" disabled>Apply fix to workspace</button>
        <button class="btn btn-ghost block" data-action="openDraftPr" disabled>Open draft PR</button>
        <button class="btn btn-ghost block" data-action="feedbackAccepted" disabled>Feedback: accepted</button>
        <button class="btn btn-ghost block" data-action="feedbackRejected" disabled>Feedback: rejected</button>
      </div>
      <p class="hint">Actions apply to the selected run. Confirm before Apply Fix writes files.</p>
    </section>

    <p class="footer-note" id="footerUrl"></p>
  </div>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    let state = { connected: false, statusText: "Checking…", runs: [], agentBaseUrl: "" };
    let tab = "guide";

    const $ = (id) => document.getElementById(id);
    const tabs = [...document.querySelectorAll(".tab")];
    const panels = {
      guide: $("panel-guide"),
      runs: $("panel-runs"),
      actions: $("panel-actions"),
    };

    function setTab(name) {
      tab = name;
      tabs.forEach((t) => {
        const on = t.dataset.tab === name;
        t.classList.toggle("active", on);
        t.setAttribute("aria-selected", on ? "true" : "false");
      });
      Object.entries(panels).forEach(([k, el]) => {
        el.classList.toggle("active", k === name);
      });
      vscode.postMessage({ type: "tab", tab: name });
    }

    function statusClass(status) {
      if (!status) return "";
      if (status.startsWith("success")) return "ok";
      if (status === "escalated" || status.includes("fail")) return "bad";
      return "warn";
    }

    function render() {
      $("status").textContent = state.statusText || (state.connected ? "Connected" : "Offline");
      $("dot").className = "dot" + (state.connected ? " ok" : "");
      $("footerUrl").textContent = state.agentBaseUrl || "";

      const runsEl = $("runs");
      runsEl.innerHTML = "";
      if (state.error) {
        const e = document.createElement("div");
        e.className = "error";
        e.textContent = state.error;
        runsEl.appendChild(e);
      } else if (!state.runs || !state.runs.length) {
        const e = document.createElement("div");
        e.className = "empty";
        e.textContent = state.connected
          ? "No runs yet. Create one via the agent API, then refresh."
          : "Agent offline. Start raphael-agent-serve, then Test connection.";
        runsEl.appendChild(e);
      } else {
        state.runs.forEach((run) => {
          const btn = document.createElement("button");
          btn.className = "run" + (run.run_id === state.selectedRunId ? " selected" : "");
          btn.type = "button";
          const fc = run.failure_class || "—";
          const repo = run.repository
            ? run.repository.owner + "/" + run.repository.name
            : "";
          btn.innerHTML =
            '<div class="run-id">' + escapeHtml(run.run_id) + "</div>" +
            '<div class="run-meta">' +
            '<span class="badge ' + statusClass(run.status) + '">' + escapeHtml(run.status) + "</span>" +
            "<span>" + escapeHtml(fc) + "</span>" +
            (repo ? "<span>" + escapeHtml(repo) + "</span>" : "") +
            "</div>";
          btn.addEventListener("click", () => {
            vscode.postMessage({ type: "selectRun", runId: run.run_id });
            setTab("actions");
          });
          btn.addEventListener("dblclick", () => {
            vscode.postMessage({ type: "openRun", runId: run.run_id });
          });
          runsEl.appendChild(btn);
        });
      }

      const selected = (state.runs || []).find((r) => r.run_id === state.selectedRunId);
      const box = $("selected");
      if (selected) {
        box.innerHTML =
          "<h2>" + escapeHtml(selected.run_id) + "</h2>" +
          '<p class="meta">' +
          escapeHtml(selected.status) +
          (selected.failure_class ? " · " + escapeHtml(selected.failure_class) : "") +
          (selected.terminal_reason ? "<br/>" + escapeHtml(selected.terminal_reason) : "") +
          "</p>";
      } else {
        box.innerHTML =
          '<h2>No run selected</h2><p class="meta">Choose a run in the Runs tab first.</p>';
      }
      document.querySelectorAll("[data-action]").forEach((el) => {
        el.disabled = !selected;
      });
    }

    function escapeHtml(s) {
      return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    tabs.forEach((t) => t.addEventListener("click", () => setTab(t.dataset.tab)));
    $("btnRefresh").addEventListener("click", () => vscode.postMessage({ type: "refresh" }));
    $("btnRefreshRuns").addEventListener("click", () => vscode.postMessage({ type: "refresh" }));
    $("btnConnect").addEventListener("click", () => vscode.postMessage({ type: "testConnection" }));
    $("btnToken").addEventListener("click", () => vscode.postMessage({ type: "setApiToken" }));
    document.querySelectorAll("[data-action]").forEach((el) => {
      el.addEventListener("click", () => {
        if (!state.selectedRunId) return;
        vscode.postMessage({ type: el.dataset.action, runId: state.selectedRunId });
      });
    });

    window.addEventListener("message", (event) => {
      const msg = event.data;
      if (msg && msg.type === "state") {
        state = msg.state || state;
        render();
      }
    });

    vscode.postMessage({ type: "ready" });
    render();
  </script>
</body>
</html>`;
  }
}

function getNonce(): string {
  const chars =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let text = "";
  for (let i = 0; i < 32; i++) {
    text += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return text;
}
