/** Resolve and apply Raphael patch payloads to the workspace. */

import * as path from "path";

export const DEFAULT_ALLOWLIST = [
  "deploy/",
  "k8s/",
  "kubernetes/",
  "manifests/",
  "charts/",
  "helm/",
  "overlays/",
  ".github/workflows/",
];

export type PatchFile = {
  path: string;
  action: string;
  content?: string | null;
  unified_diff_hunk?: string | null;
};

export type CandidatePatch = {
  patch_id?: string;
  unified_diff?: string | null;
  files?: PatchFile[];
};

export type DeliveryPlan =
  | { kind: "unified_diff"; diff: string; paths: string[] }
  | { kind: "file_contents"; files: Array<{ path: string; content: string; action: string }> };

export function pickActivePatch(run: {
  candidate_patches?: CandidatePatch[];
  active_patch_id?: string | null;
}): CandidatePatch | undefined {
  const patches = run.candidate_patches || [];
  if (!patches.length) return undefined;
  const active = run.active_patch_id;
  if (active) {
    const hit = patches.find((p) => p.patch_id === active);
    if (hit) return hit;
  }
  return patches[0];
}

/** Mirror agent delivery_patch_from_run, plus file-content fallback for stub patches. */
export function buildDeliveryPlan(run: {
  candidate_patches?: CandidatePatch[];
  active_patch_id?: string | null;
  publish?: { fix_snippet?: string | null };
}): DeliveryPlan | null {
  const patch = pickActivePatch(run);
  if (patch) {
    const ud = patch.unified_diff;
    if (typeof ud === "string" && ud.trim()) {
      return {
        kind: "unified_diff",
        diff: ud,
        paths: (patch.files || []).map((f) => f.path).filter(Boolean),
      };
    }
    const hunks = (patch.files || [])
      .map((f) => f.unified_diff_hunk)
      .filter((h): h is string => typeof h === "string" && h.trim().length > 0);
    if (hunks.length && !(patch.files || []).every((f) => f.content)) {
      // Prefer full file contents when available (stub often has both).
    }
    const withContent = (patch.files || []).filter(
      (f) =>
        (f.action === "modify" || f.action === "create") &&
        typeof f.content === "string"
    );
    if (withContent.length) {
      return {
        kind: "file_contents",
        files: withContent.map((f) => ({
          path: f.path,
          content: f.content as string,
          action: f.action,
        })),
      };
    }
    if (hunks.length) {
      return {
        kind: "unified_diff",
        diff: hunks.join("\n"),
        paths: (patch.files || []).map((f) => f.path).filter(Boolean),
      };
    }
  }
  const snippet = run.publish?.fix_snippet;
  if (typeof snippet === "string" && snippet.trim()) {
    return { kind: "unified_diff", diff: snippet, paths: [] };
  }
  return null;
}

export function normalizeRelPath(p: string): string {
  return p.replace(/\\/g, "/").replace(/^\.\//, "");
}

export function assertSafeWorkspacePath(
  workspaceRoot: string,
  relPath: string,
  allowPrefixes: string[]
): string {
  const norm = normalizeRelPath(relPath);
  if (!norm || norm.startsWith("/") || norm.includes("..")) {
    throw new Error(`refusing unsafe path: ${relPath}`);
  }
  const prefixes =
    allowPrefixes.length > 0 ? allowPrefixes : DEFAULT_ALLOWLIST;
  const allowed = prefixes.some((prefix) => {
    const p = prefix.endsWith("/") ? prefix : `${prefix}/`;
    return norm === prefix.replace(/\/$/, "") || norm.startsWith(p);
  });
  if (!allowed) {
    throw new Error(`path not in allowlist: ${norm}`);
  }
  const abs = path.resolve(workspaceRoot, norm);
  const root = path.resolve(workspaceRoot);
  if (abs !== root && !abs.startsWith(root + path.sep)) {
    throw new Error(`path escapes workspace: ${norm}`);
  }
  return abs;
}

export function planSummary(plan: DeliveryPlan): string {
  if (plan.kind === "file_contents") {
    return plan.files.map((f) => `${f.action} ${f.path}`).join("\n");
  }
  const paths = plan.paths.length ? plan.paths.join(", ") : "(diff paths unknown)";
  return `unified diff touching: ${paths}\n\n${plan.diff.slice(0, 1200)}${
    plan.diff.length > 1200 ? "\n…" : ""
  }`;
}
