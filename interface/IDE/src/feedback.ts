import * as vscode from "vscode";
import type { AgentClient } from "./agentClient";

export async function sendFeedback(
  client: AgentClient,
  runId: string,
  outcome: "accepted" | "rejected"
): Promise<void> {
  const notes = await vscode.window.showInputBox({
    prompt: `Optional notes for feedback (${outcome})`,
    placeHolder: "optional",
  });
  const result = await client.feedback(
    runId,
    outcome,
    notes === undefined || notes === "" ? undefined : notes
  );
  const eventId = (result as { feedback_event_id?: string }).feedback_event_id;
  vscode.window.showInformationMessage(
    `Raphael feedback ${outcome}${eventId ? ` (${eventId})` : ""}`
  );
}
