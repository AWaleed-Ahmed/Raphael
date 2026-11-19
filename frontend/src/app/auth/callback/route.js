// GitHub redirects here. The state must match the cookie set at login (login CSRF),
// then core exchanges the code and issues the session, which only this server holds.
import {
  SESSION_COOKIE,
  SESSION_MAX_AGE,
  STATE_COOKIE,
  clearCookie,
  coreUrl,
  readCookie,
  redirect,
  safeEqual,
  setCookie,
} from "../../../server/core.js";

export const dynamic = "force-dynamic";

export async function GET(request) {
  const params = new URL(request.url).searchParams;
  const code = params.get("code") || "";
  const state = params.get("state") || "";
  const clearState = clearCookie(STATE_COOKIE, "/auth/");
  if (!code || !safeEqual(state, readCookie(request, STATE_COOKIE))) {
    return redirect(request, "/?login=failed", [clearState]);
  }
  let session = "";
  try {
    const response = await fetch(coreUrl("/v1/auth/github/callback"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, state }),
      cache: "no-store",
    });
    const body = await response.json();
    if (response.ok && typeof body?.session_token === "string") session = body.session_token;
  } catch {
    session = "";
  }
  if (!session) return redirect(request, "/?login=failed", [clearState]);
  return redirect(request, "/console/", [clearState, setCookie(SESSION_COOKIE, session, SESSION_MAX_AGE)]);
}
