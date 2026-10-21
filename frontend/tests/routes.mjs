import assert from "node:assert/strict";

const origin = process.argv[2] || "http://localhost:3000";
for (const [path, marker] of [
  ["/", "/_next/"],
  ["/console/", "Raphael Console"],
  ["/direction/", "cloud study"],
]) {
  const response = await fetch(new URL(path, origin), { signal: AbortSignal.timeout(15000) });
  assert.equal(response.status, 200, `${path} should load`);
  const html = await response.text();
  assert.ok(html.includes(marker), `${path} should serve the correct page`);
  console.log(`OK ${path}`);
  if (path === "/console/") {
    const scripts = [...html.matchAll(/<script[^>]*src="([^"]+)"/g)];
    for (const [, source] of scripts) {
      const asset = await fetch(new URL(source, origin), { signal: AbortSignal.timeout(15000) });
      assert.equal(asset.status, 200, `${source} should load`);
      console.log(`OK ${source}`);
    }
  }
}
