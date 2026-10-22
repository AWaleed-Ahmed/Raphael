import assert from "node:assert/strict";
import { test } from "node:test";
import config from "../next.config.mjs";

test("loopback API proxy requires an explicit development opt-in", async () => {
  const previousMode = process.env.NODE_ENV;
  const previousProxy = process.env.RAPHAEL_DEV_API_PROXY;
  try {
    for (const [mode, enabled, expected] of [
      ["development", undefined, false],
      ["development", "false", false],
      ["development", "true", true],
      ["production", "true", false],
    ]) {
      process.env.NODE_ENV = mode;
      if (enabled === undefined) delete process.env.RAPHAEL_DEV_API_PROXY;
      else process.env.RAPHAEL_DEV_API_PROXY = enabled;
      const rewrites = await config.rewrites();
      const proxy = rewrites.find((rule) => rule.source.startsWith("/api/"));
      assert.equal(Boolean(proxy), expected);
      if (expected) assert.equal(proxy.destination, "http://127.0.0.1:8091/:path*");
      assert.ok(rewrites.some((rule) => rule.source === "/console/"));
    }
  } finally {
    if (previousMode === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = previousMode;
    if (previousProxy === undefined) delete process.env.RAPHAEL_DEV_API_PROXY;
    else process.env.RAPHAEL_DEV_API_PROXY = previousProxy;
  }
});
