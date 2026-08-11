import * as fs from "fs";
import * as vscode from "vscode";
import { AgentClient, AgentClientError, type RunRecord } from "./agentClient";
import {
  assertSafeWorkspacePath,
  buildDeliveryPlan,
  DEFAULT_ALLOWLIST,
  planSummary,
} from "./applyPatch";
import { sendFeedback } from "./feedback";
import { RaphaelPanelProvider, type PanelMessage } from "./panelView";
import { formatRunMarkdown } from "./runDetail";

const TOKEN_SECRET_KEY = "raphael.apiToken";

let statusBar: vscode.StatusBarItem;
let panel: RaphaelPanelProvider;
let lastSelectedRunId: string | undefined;

export async function activate(
  context: vscode.ExtensionContext
): Promise<void> {
  statusBar = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    100
  );
  statusBar.command = "raphael.testConnection";
  statusBar.text = "Raphael: …";
  statusBar.show();
  context.subscriptions.push(statusBar);

  panel = new RaphaelPanelProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      RaphaelPanelProvider.viewType,
      panel,
      { webviewOptions: { retainContextWhenHidden: true } }
    )
  );

  const getClient = async (): Promise<AgentClient> => {
    const cfg = vscode.workspace.getConfiguration("raphael");
    const baseUrl =
      cfg.get<string>("agentBaseUrl") || "http://127.0.0.1:8091";
    const token = await context.secrets.get(TOKEN_SECRET_KEY);
    return new AgentClient(baseUrl, token || undefined);
  };

  const agentBaseUrl = (): string => {
    const cfg = vscode.workspace.getConfiguration("raphael");
    return cfg.get<string>("agentBaseUrl") || "http://127.0.0.1:8091";
  };

  const refreshStatus = async (): Promise<boolean> => {
    try {
      const client = await getClient();
      await client.health();
      let suffix = "Connected";
      try {
        const gn = await client.goNogo();
        if (gn.recommendation) {
          suffix = gn.go ? "Connected · go" : "Connected · no-go";
        }
      } catch {
        /* go-nogo optional */
      }
      statusBar.text = `Raphael: ${suffix}`;
      statusBar.tooltip = agentBaseUrl();
      panel.update({
        connected: true,
        statusText: suffix,
        agentBaseUrl: agentBaseUrl(),
      });
      return true;
    } catch {
      statusBar.text = "Raphael: Offline";
      statusBar.tooltip =
        "Agent unreachable — start raphael-agent-serve on :8091";
      panel.update({
        connected: false,
        statusText: "Offline",
        agentBaseUrl: agentBaseUrl(),
        error: "Agent unreachable at " + agentBaseUrl(),
      });
      return false;
    }
  };

  const refreshRuns = async (): Promise<void> => {
    try {
      const client = await getClient();
      const listed = await client.listRuns({ limit: 20 });
      panel.update({
        runs: listed.runs,
        error: null,
        connected: true,
        statusText: panel.getState().statusText || "Connected",
        agentBaseUrl: agentBaseUrl(),
      });
    } catch (err) {
      const msg =
        err instanceof AgentClientError ? err.message : String(err);
      panel.update({
        runs: [],
        error: msg,
        connected: false,
        statusText: "Offline",
        agentBaseUrl: agentBaseUrl(),
      });
    }
  };

  const resolveRunId = async (arg?: unknown): Promise<string | undefined> => {
    if (typeof arg === "string" && arg.trim()) {
      return arg.trim();
    }
    if (lastSelectedRunId) {
      return lastSelectedRunId;
    }
    const fromPanel = panel.getState().selectedRunId;
    if (fromPanel) return fromPanel;
    return vscode.window.showInputBox({
      prompt: "Raphael run_id",
      placeHolder: "run-…",
    });
  };

  const selectRun = (runId: string): void => {
    lastSelectedRunId = runId;
    panel.update({ selectedRunId: runId });
  };

  const handlePanelMessage = async (msg: PanelMessage): Promise<void> => {
    switch (msg.type) {
      case "ready":
        await refreshStatus();
        await refreshRuns();
        break;
      case "refresh":
        await refreshStatus();
        await refreshRuns();
        break;
      case "testConnection":
        await vscode.commands.executeCommand("raphael.testConnection");
        break;
      case "setApiToken":
        await vscode.commands.executeCommand("raphael.setApiToken");
        break;
      case "selectRun":
        selectRun(msg.runId);
        break;
      case "openRun":
        selectRun(msg.runId);
        await vscode.commands.executeCommand(
          "raphael.showRunMarkdown",
          msg.runId
        );
        break;
      case "applyFix":
        selectRun(msg.runId);
        await vscode.commands.executeCommand("raphael.applyFix", msg.runId);
        break;
      case "openDraftPr":
        selectRun(msg.runId);
        await vscode.commands.executeCommand(
          "raphael.openDraftPr",
          msg.runId
        );
        break;
      case "feedbackAccepted":
        selectRun(msg.runId);
        await vscode.commands.executeCommand(
          "raphael.feedbackAccepted",
          msg.runId
        );
        break;
      case "feedbackRejected":
        selectRun(msg.runId);
        await vscode.commands.executeCommand(
          "raphael.feedbackRejected",
          msg.runId
        );
        break;
      case "tab":
        break;
      default:
        break;
    }
  };

  panel.setHandlers({ onMessage: handlePanelMessage });

  context.subscriptions.push(
    vscode.commands.registerCommand("raphael.testConnection", async () => {
      const ok = await refreshStatus();
      if (ok) {
        vscode.window.showInformationMessage("Raphael agent is reachable.");
        await refreshRuns();
      } else {
        vscode.window.showErrorMessage(
          "Raphael agent unreachable. Start raphael-agent-serve on :8091."
        );
      }
    }),
    vscode.commands.registerCommand("raphael.refreshRuns", () =>
      refreshRuns()
    ),
    vscode.commands.registerCommand("raphael.focusPanel", async () => {
      await vscode.commands.executeCommand("raphael.panel.focus");
    }),
    vscode.commands.registerCommand("raphael.setApiToken", async () => {
      const token = await vscode.window.showInputBox({
        prompt: "Raphael API token (RAPHAEL_INTERFACE_TOKEN)",
        password: true,
        placeHolder: "leave empty to clear",
      });
      if (token === undefined) return;
      if (token === "") {
        await context.secrets.delete(TOKEN_SECRET_KEY);
      } else {
        await context.secrets.store(TOKEN_SECRET_KEY, token);
      }
      vscode.window.showInformationMessage("Raphael API token updated.");
      await refreshStatus();
    }),
    vscode.commands.registerCommand("raphael.openRun", async () => {
      const runId = await vscode.window.showInputBox({
        prompt: "Open Raphael run_id",
        placeHolder: "run-…",
      });
      if (!runId) return;
      selectRun(runId);
      await vscode.commands.executeCommand("raphael.showRunMarkdown", runId);
    }),
    vscode.commands.registerCommand(
      "raphael.showRunMarkdown",
      async (arg?: unknown) => {
        const runId = await resolveRunId(arg);
        if (!runId) return;
        selectRun(runId);
        try {
          const client = await getClient();
          const run = await client.getRun(runId);
          const doc = await vscode.workspace.openTextDocument({
            content: formatRunMarkdown(run),
            language: "markdown",
          });
          await vscode.window.showTextDocument(doc, { preview: true });
        } catch (err) {
          vscode.window.showErrorMessage(
            err instanceof Error ? err.message : String(err)
          );
        }
      }
    ),
    vscode.commands.registerCommand(
      "raphael.openDraftPr",
      async (arg?: unknown) => {
        const runId = await resolveRunId(arg);
        if (!runId) return;
        selectRun(runId);
        try {
          const client = await getClient();
          const run = await client.getRun(runId);
          const url = run.pull_request_url;
          if (!url) {
            vscode.window.showWarningMessage(
              "No pull_request_url on this run."
            );
            return;
          }
          await vscode.env.openExternal(vscode.Uri.parse(url));
        } catch (err) {
          vscode.window.showErrorMessage(
            err instanceof Error ? err.message : String(err)
          );
        }
      }
    ),
    vscode.commands.registerCommand(
      "raphael.feedbackAccepted",
      async (arg?: unknown) => {
        const runId = await resolveRunId(arg);
        if (!runId) return;
        selectRun(runId);
        try {
          await sendFeedback(await getClient(), runId, "accepted");
        } catch (err) {
          vscode.window.showErrorMessage(
            err instanceof Error ? err.message : String(err)
          );
        }
      }
    ),
    vscode.commands.registerCommand(
      "raphael.feedbackRejected",
      async (arg?: unknown) => {
        const runId = await resolveRunId(arg);
        if (!runId) return;
        selectRun(runId);
        try {
          await sendFeedback(await getClient(), runId, "rejected");
        } catch (err) {
          vscode.window.showErrorMessage(
            err instanceof Error ? err.message : String(err)
          );
        }
      }
    ),
    vscode.commands.registerCommand(
      "raphael.applyFix",
      async (arg?: unknown) => {
        const runId = await resolveRunId(arg);
        if (!runId) return;
        selectRun(runId);
        const folder = vscode.workspace.workspaceFolders?.[0];
        if (!folder) {
          vscode.window.showErrorMessage(
            "Open a workspace folder before applying a fix."
          );
          return;
        }
        try {
          const client = await getClient();
          const run = await client.getRun(runId);
          await applyFixToWorkspace(folder.uri.fsPath, run);
        } catch (err) {
          vscode.window.showErrorMessage(
            err instanceof Error ? err.message : String(err)
          );
        }
      }
    )
  );

  void refreshStatus().then(() => refreshRuns());
  const poll = setInterval(() => {
    void refreshStatus();
  }, 30_000);
  context.subscriptions.push({ dispose: () => clearInterval(poll) });
}

async function applyFixToWorkspace(
  workspaceRoot: string,
  run: RunRecord
): Promise<void> {
  const plan = buildDeliveryPlan(run);
  if (!plan) {
    throw new Error("No delivery patch / file contents on this run");
  }
  const prefixes =
    run.fix_rules?.writable_path_prefixes?.filter(Boolean) ||
    DEFAULT_ALLOWLIST;

  const confirm = await vscode.window.showWarningMessage(
    `Apply Raphael fix from ${run.run_id} to workspace?\n\n${planSummary(plan).slice(0, 800)}`,
    { modal: true },
    "Apply to workspace"
  );
  if (confirm !== "Apply to workspace") {
    return;
  }

  if (plan.kind === "file_contents") {
    const edit = new vscode.WorkspaceEdit();
    for (const file of plan.files) {
      const abs = assertSafeWorkspacePath(
        workspaceRoot,
        file.path,
        prefixes
      );
      const uri = vscode.Uri.file(abs);
      if (!fs.existsSync(abs)) {
        edit.createFile(uri, { ignoreIfExists: true });
        edit.insert(uri, new vscode.Position(0, 0), file.content);
      } else {
        const doc = await vscode.workspace.openTextDocument(uri);
        const full = new vscode.Range(
          doc.positionAt(0),
          doc.positionAt(doc.getText().length)
        );
        edit.replace(uri, full, file.content);
      }
    }
    const ok = await vscode.workspace.applyEdit(edit);
    if (!ok) throw new Error("WorkspaceEdit failed");
    vscode.window.showInformationMessage(
      `Applied ${plan.files.length} file(s) from ${run.run_id}`
    );
    return;
  }

  throw new Error(
    "This run only has a unified diff without full file contents. " +
      "Re-run with a patch that includes files[].content (recorded_stub does), " +
      "or apply the draft PR in GitHub."
  );
}

export function deactivate(): void {
  /* noop */
}
