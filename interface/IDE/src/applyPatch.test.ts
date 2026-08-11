import * as assert from "assert";
import * as path from "path";
import { describe, it } from "node:test";
import {
  assertSafeWorkspacePath,
  buildDeliveryPlan,
  DEFAULT_ALLOWLIST,
} from "./applyPatch";

describe("buildDeliveryPlan", () => {
  it("prefers file contents when unified_diff is null", () => {
    const plan = buildDeliveryPlan({
      active_patch_id: "patch-1",
      candidate_patches: [
        {
          patch_id: "patch-1",
          unified_diff: null,
          files: [
            {
              path: "deploy/manifests/broken.yaml",
              action: "modify",
              content: "apiVersion: v1\n",
              unified_diff_hunk: "-9090\n+8080\n",
            },
          ],
        },
      ],
    });
    assert.ok(plan);
    assert.equal(plan!.kind, "file_contents");
    if (plan!.kind === "file_contents") {
      assert.equal(plan.files[0].path, "deploy/manifests/broken.yaml");
    }
  });
});

describe("assertSafeWorkspacePath", () => {
  const root = path.resolve("/tmp/raphael-ws");

  it("allows deploy/ paths", () => {
    const abs = assertSafeWorkspacePath(
      root,
      "deploy/manifests/broken.yaml",
      DEFAULT_ALLOWLIST
    );
    assert.ok(abs.includes("deploy"));
  });

  it("rejects path escape", () => {
    assert.throws(() =>
      assertSafeWorkspacePath(root, "../etc/passwd", DEFAULT_ALLOWLIST)
    );
  });

  it("rejects non-allowlisted path", () => {
    assert.throws(() =>
      assertSafeWorkspacePath(root, "secrets/key.pem", DEFAULT_ALLOWLIST)
    );
  });
});
