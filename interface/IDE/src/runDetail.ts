import type { RunRecord } from "./agentClient";
import { buildDeliveryPlan, planSummary } from "./applyPatch";

export function formatRunMarkdown(run: RunRecord): string {
  const diagnosis = run.diagnosis || {};
  const classification = diagnosis.classification || {};
  const publish = (run.publish || {}) as Record<string, unknown>;
  const plan = buildDeliveryPlan(run);
  const lines = [
    `# Raphael run \`${run.run_id}\``,
    "",
    `- **Status:** ${run.status}`,
    `- **Class:** ${classification.failure_class || "—"} (confidence ${diagnosis.confidence ?? "—"})`,
    `- **Terminal:** ${(run as { terminal_reason?: string }).terminal_reason || "—"}`,
    `- **Sandbox mode:** ${(run as { sandbox_mode?: string }).sandbox_mode || "—"}`,
    `- **Result id:** ${(run as { result_id?: string }).result_id || "—"}`,
    "",
    "## Delivery",
    "",
    `- **Draft PR:** ${run.pull_request_url || "—"}`,
    `- **Publish dry_run:** ${String(publish.dry_run ?? "—")}`,
    "",
    "## Patch plan",
    "",
    "```",
    plan ? planSummary(plan) : "(no delivery_patch / file contents)",
    "```",
    "",
    "## Commands",
    "",
    "- Raphael: Apply Fix from Run",
    "- Raphael: Open Draft PR",
    "- Raphael: Feedback Accepted / Rejected",
    "",
  ];
  return lines.join("\n");
}
