import * as vscode from "vscode";
import type { RunSummary } from "./agentClient";

export class RunItem extends vscode.TreeItem {
  constructor(public readonly summary: RunSummary) {
    const fc = summary.failure_class || "unknown";
    super(`${summary.run_id}`, vscode.TreeItemCollapsibleState.None);
    this.description = `${summary.status} · ${fc}`;
    this.tooltip = [
      summary.run_id,
      summary.status,
      summary.terminal_reason || "",
      `${summary.repository.owner}/${summary.repository.name}`,
    ]
      .filter(Boolean)
      .join("\n");
    this.contextValue = "raphaelRun";
    this.iconPath = new vscode.ThemeIcon(
      summary.status.startsWith("success")
        ? "pass"
        : summary.status === "escalated"
          ? "warning"
          : "circle-outline"
    );
    this.command = {
      command: "raphael.showRunMarkdown",
      title: "Show Run",
      arguments: [summary.run_id],
    };
  }
}

export class RunsTreeProvider
  implements vscode.TreeDataProvider<RunItem>
{
  private _onDidChangeTreeData = new vscode.EventEmitter<
    RunItem | undefined | null | void
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private runs: RunSummary[] = [];
  private errorMessage: string | null = null;

  refresh(runs: RunSummary[], error?: string | null): void {
    this.runs = runs;
    this.errorMessage = error || null;
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: RunItem): vscode.TreeItem {
    return element;
  }

  getChildren(): Thenable<RunItem[]> {
    if (this.errorMessage) {
      const item = new vscode.TreeItem(
        this.errorMessage,
        vscode.TreeItemCollapsibleState.None
      ) as RunItem;
      return Promise.resolve([item]);
    }
    return Promise.resolve(this.runs.map((r) => new RunItem(r)));
  }
}
