// Server-only helpers for talking to raphael-core from Next.js route handlers.
// See docs/auth-tenancy-design-2026-11-18.md, decision 3. Never import from client code.
import { timingSafeEqual } from "node:crypto";

export const SESSION_COOKIE = "raphael_session";
export const STATE_COOKIE = "raphael_oauth_state";
export const SESSION_MAX_AGE = 7 * 24 * 60 * 60;
export const STATE_MAX_AGE = 10 * 60;

export function coreUrl(path) {
  const base = (process.env.RAPHAEL_CORE_URL || "").trim().replace(/\/+$/, "");
  if (!base) throw new Error("RAPHAEL_CORE_URL is not configured");
  return `${base}${path}`;
}

export function readCookie(request, name) {
  for (const part of (request.headers.get("cookie") || "").split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return "";
}

export function setCookie(name, value, maxAge, path = "/") {
  return `${name}=${encodeURIComponent(value)}; Path=${path}; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=Lax`;
}

export function clearCookie(name, path = "/") {
  return setCookie(name, "", 0, path);
}

export function safeEqual(a, b) {
  const left = Buffer.from(String(a));
  const right = Buffer.from(String(b));
  return left.length > 0 && left.length === right.length && timingSafeEqual(left, right);
}

// Mutating requests must come from this site: SameSite=Lax already withholds the
// session cookie from cross-site POSTs, and this check also covers same-site subdomains.
export function sameOrigin(request) {
  const origin = request.headers.get("origin");
  return Boolean(origin) && origin === new URL(request.url).origin;
}

export function redirect(request, location, cookies = []) {
  const headers = new Headers({ Location: new URL(location, request.url).toString(), "Cache-Control": "no-store" });
  for (const value of cookies) headers.append("Set-Cookie", value);
  return new Response(null, { status: 303, headers });
}

export function jsonError(status, code, message) {
  return Response.json({ error: { code, message, retryable: false } }, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}
