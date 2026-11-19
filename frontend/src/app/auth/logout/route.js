// Revoke the session in core and drop the cookie. POST only, from this site only.
import { SESSION_COOKIE, clearCookie, coreUrl, jsonError, readCookie, redirect, sameOrigin } from "../../../server/core.js";

export const dynamic = "force-dynamic";

export async function POST(request) {
  if (!sameOrigin(request)) return jsonError(403, "forbidden", "cross-origin logout refused");
  const session = readCookie(request, SESSION_COOKIE);
  if (session) {
    try {
      await fetch(coreUrl("/v1/auth/logout"), {
        method: "POST",
        headers: { Authorization: `Bearer ${session}` },
        cache: "no-store",
      });
    } catch {
      // The cookie is cleared regardless; an unreachable core cannot keep a user signed in here.
    }
  }
  return redirect(request, "/", [clearCookie(SESSION_COOKIE)]);
}
