// Start GitHub App login: core issues a single-use state; bind it to this browser.
import { STATE_COOKIE, STATE_MAX_AGE, coreUrl, redirect, setCookie } from "../../../server/core.js";

export const dynamic = "force-dynamic";

export async function GET(request) {
  let start;
  try {
    const response = await fetch(coreUrl("/v1/auth/github/start"), { cache: "no-store" });
    if (!response.ok) throw new Error(`core returned ${response.status}`);
    start = await response.json();
    if (typeof start?.authorize_url !== "string" || typeof start?.state !== "string") throw new Error("bad start response");
  } catch {
    return redirect(request, "/?login=unavailable");
  }
  return redirect(request, start.authorize_url, [setCookie(STATE_COOKIE, start.state, STATE_MAX_AGE, "/auth/")]);
}
