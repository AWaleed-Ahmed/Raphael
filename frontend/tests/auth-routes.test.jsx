import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

import { GET as login } from "../src/app/auth/login/route.js";
import { GET as callback } from "../src/app/auth/callback/route.js";
import { POST as logout } from "../src/app/auth/logout/route.js";
import { DELETE as proxyDelete, GET as proxyGet, POST as proxyPost } from "../src/app/api/core/[...path]/route.js";

const SITE = "https://raphael.example";
const CORE = "https://core.example";
const realFetch = globalThis.fetch;
let calls;

beforeEach(() => {
  process.env.RAPHAEL_CORE_URL = `${CORE}/`;
  calls = [];
});

afterEach(() => {
  globalThis.fetch = realFetch;
  delete process.env.RAPHAEL_CORE_URL;
});

function mockCore(handler) {
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), init });
    return handler(String(url), init);
  };
}

function req(path, { method = "GET", cookie = "", origin, headers = {}, body } = {}) {
  const all = { ...headers };
  if (cookie) all.cookie = cookie;
  if (origin) all.origin = origin;
  return new Request(`${SITE}${path}`, { method, headers: all, body });
}

const ctx = (...path) => ({ params: Promise.resolve({ path }) });
const cookies = (response) => response.headers.getSetCookie();

test("login stores core's state in a scoped HttpOnly cookie and redirects to GitHub", async () => {
  mockCore(() => Response.json({ authorize_url: "https://github.com/login/oauth/authorize?state=s1", state: "s1" }));
  const response = await login(req("/auth/login/"));
  assert.equal(response.status, 303);
  assert.equal(response.headers.get("location"), "https://github.com/login/oauth/authorize?state=s1");
  assert.equal(calls[0].url, `${CORE}/v1/auth/github/start`);
  const [state] = cookies(response);
  assert.match(state, /^raphael_oauth_state=s1; Path=\/auth\/; Max-Age=600; HttpOnly; Secure; SameSite=Lax$/);
});

test("login falls back to the landing page when core is unavailable", async () => {
  mockCore(() => new Response("no", { status: 503 }));
  const response = await login(req("/auth/login/"));
  assert.equal(response.headers.get("location"), `${SITE}/?login=unavailable`);
  assert.deepEqual(cookies(response), []);
});

test("callback rejects a state that does not match the cookie", async () => {
  mockCore(() => assert.fail("core must not be called"));
  for (const cookie of ["", "raphael_oauth_state=other"]) {
    const response = await callback(req("/auth/callback/?code=c&state=s1", { cookie }));
    assert.equal(response.headers.get("location"), `${SITE}/?login=failed`);
    assert.ok(!cookies(response).some((value) => value.startsWith("raphael_session=")));
  }
});

test("callback exchanges through core and sets the session cookie", async () => {
  mockCore(() => Response.json({ session_token: "rs_abc", github_login: "octo", tenants: [] }));
  const response = await callback(req("/auth/callback/?code=c1&state=s1", { cookie: "raphael_oauth_state=s1" }));
  assert.equal(response.headers.get("location"), `${SITE}/console/`);
  assert.equal(calls[0].url, `${CORE}/v1/auth/github/callback`);
  assert.deepEqual(JSON.parse(calls[0].init.body), { code: "c1", state: "s1" });
  const set = cookies(response);
  assert.ok(set.includes("raphael_oauth_state=; Path=/auth/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"));
  assert.ok(set.includes("raphael_session=rs_abc; Path=/; Max-Age=604800; HttpOnly; Secure; SameSite=Lax"));
});

test("callback fails closed when core rejects the login", async () => {
  mockCore(() => Response.json({ error: { message: "login failed" } }, { status: 502 }));
  const response = await callback(req("/auth/callback/?code=c1&state=s1", { cookie: "raphael_oauth_state=s1" }));
  assert.equal(response.headers.get("location"), `${SITE}/?login=failed`);
  assert.ok(!cookies(response).some((value) => value.startsWith("raphael_session=rs")));
});

test("proxy requires a session and forwards it as a bearer with the tenant", async () => {
  mockCore(() => Response.json({ runs: [] }, { headers: { "set-cookie": "core=leak" } }));
  assert.equal((await proxyGet(req("/api/core/v1/runs/"), ctx("v1", "runs"))).status, 401);
  assert.equal(calls.length, 0);
  const response = await proxyGet(
    req("/api/core/v1/runs/?limit=5", { cookie: "raphael_session=rs_abc", headers: { "x-raphael-tenant": "gh-1" } }),
    ctx("v1", "runs"),
  );
  assert.equal(response.status, 200);
  assert.equal(calls[0].url, `${CORE}/v1/runs?limit=5`);
  assert.equal(calls[0].init.headers.Authorization, "Bearer rs_abc");
  assert.equal(calls[0].init.headers["X-Raphael-Tenant"], "gh-1");
  assert.equal(response.headers.get("set-cookie"), null);
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("proxy only reaches console endpoints", async () => {
  mockCore(() => assert.fail("core must not be called"));
  for (const path of [["v1", "webhooks", "github"], ["v1", "tenants", "gh-1", "jobs", "next"], ["v1", "results"], ["health"]]) {
    const response = await proxyGet(req("/api/core/x/", { cookie: "raphael_session=rs_abc" }), ctx(...path));
    assert.equal(response.status, 404, path.join("/"));
  }
});

test("proxy refuses cross-origin writes and forwards same-origin ones", async () => {
  mockCore(() => Response.json({ revoked: true }));
  const cookie = "raphael_session=rs_abc";
  assert.equal((await proxyDelete(req("/api/core/v1/connectors/c1/", { method: "DELETE", cookie }), ctx("v1", "connectors", "c1"))).status, 403);
  assert.equal((await proxyPost(req("/api/core/v1/connectors/", { method: "POST", cookie, origin: "https://evil.example" }), ctx("v1", "connectors"))).status, 403);
  assert.equal(calls.length, 0);
  const response = await proxyPost(
    req("/api/core/v1/connectors/", { method: "POST", cookie, origin: SITE, headers: { "content-type": "application/json" }, body: '{"label":"x"}' }),
    ctx("v1", "connectors"),
  );
  assert.equal(response.status, 200);
  assert.equal(calls[0].init.method, "POST");
  assert.equal(new TextDecoder().decode(calls[0].init.body), '{"label":"x"}');
});

test("proxy reports an unreachable core as 502", async () => {
  mockCore(() => { throw new TypeError("fetch failed"); });
  const response = await proxyGet(req("/api/core/v1/me/", { cookie: "raphael_session=rs_abc" }), ctx("v1", "me"));
  assert.equal(response.status, 502);
});

test("logout is same-origin only, revokes in core and clears the cookie", async () => {
  mockCore(() => Response.json({ logged_out: true }));
  assert.equal((await logout(req("/auth/logout/", { method: "POST", cookie: "raphael_session=rs_abc", origin: "https://evil.example" }))).status, 403);
  assert.equal(calls.length, 0);
  const response = await logout(req("/auth/logout/", { method: "POST", cookie: "raphael_session=rs_abc", origin: SITE }));
  assert.equal(response.headers.get("location"), `${SITE}/`);
  assert.equal(calls[0].url, `${CORE}/v1/auth/logout`);
  assert.equal(calls[0].init.headers.Authorization, "Bearer rs_abc");
  assert.ok(cookies(response).includes("raphael_session=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"));
});
