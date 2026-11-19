// Authenticated proxy: the browser holds only an HttpOnly cookie; this server
// attaches the core session as a bearer token. Only console endpoints pass.
import { SESSION_COOKIE, coreUrl, jsonError, readCookie, sameOrigin } from "../../../../server/core.js";

export const dynamic = "force-dynamic";

const ALLOWED = [
  /^v1\/me$/,
  /^v1\/runs$/,
  /^v1\/runs\/[\w.-]+$/,
  /^v1\/runs\/[\w.-]+\/actions$/,
  /^v1\/connectors$/,
  /^v1\/connectors\/[\w.-]+$/,
  /^v1\/feedback$/,
  /^v1\/metrics$/,
];

async function forward(request, context) {
  const { path = [] } = await context.params;
  const target = path.join("/");
  if (!ALLOWED.some((rule) => rule.test(target))) return jsonError(404, "not_found", "unknown endpoint");
  if (!["GET", "HEAD"].includes(request.method) && !sameOrigin(request)) {
    return jsonError(403, "forbidden", "cross-origin request refused");
  }
  const session = readCookie(request, SESSION_COOKIE);
  if (!session) return jsonError(401, "unauthorized", "sign in required");

  const headers = { Authorization: `Bearer ${session}`, Accept: "application/json" };
  const tenant = request.headers.get("x-raphael-tenant");
  if (tenant) headers["X-Raphael-Tenant"] = tenant;
  const contentType = request.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;

  let upstream;
  try {
    upstream = await fetch(coreUrl(`/${target}${new URL(request.url).search}`), {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return jsonError(502, "upstream_error", "core is unreachable");
  }
  // Rebuild headers: never pass core cookies or hop-by-hop headers to the browser.
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") || "application/json",
      "Cache-Control": "no-store",
    },
  });
}

export const GET = forward;
export const POST = forward;
export const DELETE = forward;
