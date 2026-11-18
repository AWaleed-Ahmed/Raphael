# Auth and tenancy design (2026-11-18)

Status: **approved 2026-11-18, implementation pending.** Tracks #95, sections 2 and 3.

## Goal

Let anyone sign in with GitHub, install the Raphael GitHub App on their
account or org, connect their own Ignis, and see only their own runs, with no
operator editing environment variables.

Constraints from #95, section 0:
- free tiers only;
- a single core instance on the Oracle VM;
- the frontend on Vercel Hobby;
- users run Ignis themselves.

## What exists today

Every identity decision goes through one abstraction: **bearer token →
principal** (`tenant_id`, `role`, `repositories`, optional
`company_id`/`client_id`). There are three lookups, all backed by static JSON in
environment variables:

| Surface | Code | Lookup | Roles |
|---|---|---|---|
| Interface API (`/v1/runs`, actions, metrics) | `agent/raphael_agent/http_api/auth.py` | `RAPHAEL_INTERFACE_TOKENS` (or the single `RAPHAEL_INTERFACE_TOKEN`) | reader, producer, operator |
| Dispatch (`/v1/tenants/{t}/jobs…`) | `dispatch/raphael_dispatch/auth.py` | `RAPHAEL_DISPATCH_TOKENS` | producer, connector |
| GitHub webhooks | `agent/raphael_agent/ingest/github.py` | `RAPHAEL_GITHUB_INSTALLATIONS` (installation ID → repo → tenant) | producer |

Run state uses `RunStore` (JSON files, or SQLite with `RAPHAEL_AGENT_STORE=sqlite`)
under `RAPHAEL_AGENT_DATA_DIR`. Dispatch job state is in memory, with persisted
leases.

**The abstraction is right. The only problem is that its backing store is a
static env var.** The design keeps the principal types and the
authorization checks exactly as they are, and replaces where the
token-to-principal mapping comes from.

## Decisions proposed

### 1. A tenant is a GitHub App installation account

- **Creation:** installing the Raphael GitHub App on a user or org creates one
  tenant. The `installation` webhook (`created`) carries the account and the
  installer. The tenant ID is derived from the installation's account ID, which
  is stable across renames.
- **Repositories:** the tenant's repos are the installation's selected repos,
  kept in sync from `installation_repositories` webhooks.
- **Removal:** uninstalling (`installation.deleted`) disables the tenant and
  revokes its connector credentials. Data is kept until the deletion policy
  (#87) removes it.

`company_id` and `client_id` stay optional and unset for public tenants; the
existing scope checks already treat them as optional.

### 2. GitHub decides membership; Raphael doesn't keep its own

- **Login:** users sign in through the GitHub App's own user authorization flow
  (one app, no separate OAuth app).
- **Access:** at login, core calls `GET /user/installations` with the user's
  token. The installations returned are exactly the tenants the user can open.
- **Roles:** an installation the user can administer maps to `operator`; any
  other installation maps to `reader`.
- **No invites in v1.** Org access follows GitHub org permissions, so there's
  no invite system, members table or role editor to build. A user who loses
  repo access on GitHub loses it in Raphael at their next session refresh.

### 3. Core issues opaque sessions; the frontend never holds GitHub tokens

```
browser ──cookie──▶ Next.js on Vercel (server routes) ──Bearer rs_…──▶ raphael-core
                         │                                                   │
                         └── OAuth code ──▶ core /v1/auth/github/callback ───┘
                                               (core exchanges the code,
                                                calls /user/installations,
                                                issues session rs_…)
```

1. The Next.js login route redirects to GitHub's authorize URL. The `state`
   value is bound to a cookie.
2. GitHub redirects back to a Next.js route, which forwards the code to core.
   **Core** exchanges it (the app's client secret lives only on core), fetches
   the user and their installations, and creates a session.
3. Core returns an opaque session token (`rs_` + 32 random bytes). Next.js
   stores it in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie on the Vercel
   domain.
4. Every console API call goes through a Next.js server route. That route reads
   the cookie and calls core with `Authorization: Bearer rs_…`. Nothing
   sensitive ships in the browser bundle, and no cross-site cookies or CORS are
   needed.
5. Core resolves `rs_…` through the **same `check_interface_auth` path** to an
   `InterfacePrincipal` for the selected tenant. The tenant comes from a
   `X-Raphael-Tenant` header and must be one of the session's installations.
   Otherwise the request gets 403.

The GitHub user token is used during login and then discarded; Raphael never
stores it. Sessions expire after 7 days, and logout or uninstall revokes them.
A session refresh re-reads `/user/installations`.

### 4. Connector credentials are issued in the UI and stored hashed

- **Issuing:** an `operator` creates an Ignis connector credential with
  `POST /v1/connectors`. The raw token (`rc_` + 32 random bytes) is shown
  **once**, as part of a one-line install command.
- **Storage:** core stores only `sha256(token)`, the tenant, the connector ID,
  `created_at`, `last_used_at` and `revoked_at`.
- **Revoking:** an operator calls `DELETE /v1/connectors/{id}`.
- **Resolution:** the dispatch resolver looks up the hash and returns the
  existing `Principal(tenant_id, "connector", connector_id)`. The lease and
  claim checks are unchanged.
- **Producer role:** the producer role stays internal; the in-process bridge
  needs no token.

### 5. Storage: SQLite on the VM's persistent disk, not Postgres, for v1

| Option | Fit for v1 |
|---|---|
| **SQLite on `/data`** (the existing `RAPHAEL_AGENT_STORE=sqlite` path) | Free, nothing extra to run, survives restarts on the Oracle VM disk, and matches the single-instance limit core already has. |
| Supabase free Postgres | Free projects **pause after about a week of low activity**. A quiet webhook service would go dark. The 500 MB cap is also tight. |
| Postgres on the same VM | Free, but adds a second service to operate and back up, for no v1 benefit while core is single-instance. |

The identity tables go in one SQLite file next to the run store. All access goes
through a small repository class, so moving to Postgres later (once
multi-instance is real) is a contained change. Back up with a nightly
`sqlite3 .backup` to block storage (covered by #87).

This drops "migrate to Postgres" from v1. It stays relevant only if the
backend moves to a host with an ephemeral disk.

### 6. Env-var credentials remain as a fallback

The resolvers check the database first, then the existing env JSON. Local
development, CI, kind proofs and existing tests keep working unchanged. A
production profile flag (`RAPHAEL_AUTH_SOURCE=db`) disables the env fallback.

## Schema (SQLite, identity file)

```sql
tenants        (tenant_id TEXT PK, github_account_id INTEGER UNIQUE, github_login TEXT,
                account_type TEXT, installation_id INTEGER UNIQUE, status TEXT,
                created_at TEXT, disabled_at TEXT)
tenant_repos   (tenant_id TEXT, repo_full_name TEXT, PRIMARY KEY (tenant_id, repo_full_name))
users          (github_user_id INTEGER PK, github_login TEXT, created_at TEXT, last_login_at TEXT)
sessions       (token_sha256 TEXT PK, github_user_id INTEGER, created_at TEXT, expires_at TEXT,
                revoked_at TEXT)
session_access (token_sha256 TEXT, tenant_id TEXT, role TEXT,  -- snapshot of /user/installations
                PRIMARY KEY (token_sha256, tenant_id))
connectors     (connector_id TEXT PK, tenant_id TEXT, token_sha256 TEXT UNIQUE, label TEXT,
                created_by INTEGER, created_at TEXT, last_used_at TEXT, revoked_at TEXT)
```

## New endpoints (core)

| Method and path | Auth | Purpose |
|---|---|---|
| `GET /v1/auth/github/start` | none | Returns the authorize URL and `state` |
| `POST /v1/auth/github/callback` | `state` check | Exchanges the code and returns a session token plus the tenant list |
| `POST /v1/auth/logout` | session | Revokes the session |
| `GET /v1/me` | session | User, tenants and roles |
| `GET/POST /v1/connectors`, `DELETE /v1/connectors/{id}` | session, `operator` | List, create and revoke Ignis credentials |
| `GET /v1/connectors/status` | session | Last poll, version and contract compatibility per connector |

The webhook route gains handlers for `installation` and
`installation_repositories`. These are verified by the existing HMAC
`RAPHAEL_GITHUB_WEBHOOK_SECRET` check.

## Security notes

- **Tokens:** credentials are random (`secrets.token_urlsafe(32)`) and stored
  only as SHA-256. A lookup by hash gives no timing signal about token contents.
- **Webhooks:** webhook HMAC is mandatory whenever `RAPHAEL_AUTH_SOURCE=db`.
- **OAuth:** `state` is single-use and expires after 10 minutes, which stops
  login CSRF. Callback errors are generic.
- **Rate limits:** the auth endpoints and connector creation get per-IP and
  per-tenant limits (in memory is fine for one instance).
- **Isolation:** tenant isolation keeps using the existing `InterfacePrincipal.allows` and
  `Principal.allows` checks, plus the tenant-scoped incident similarity from #64.
  No new authorization logic sits on the request path.
- **Secrets:** the app private key, client secret and webhook secret stay in the
  VM environment, never in the database or on Vercel.

## Delivery plan (one PR each, each shippable)

1. **Identity store and resolvers.** Add the SQLite identity tables, a
   repository class and DB-first resolvers for interface and dispatch, with the
   env fallback kept. No behavior change while the database is empty. Tests
   cover hash lookup, revocation, expiry and the fallback order.
2. **Installation lifecycle.** Add `installation` and
   `installation_repositories` webhooks, which create, update and disable
   tenants and their repos. Webhook-to-tenant mapping reads the database.
3. **Connector credentials.** Add the create/list/revoke API and DB-backed
   dispatch auth, with an end-to-end check that a UI-issued token can poll.
4. **Login.** Add the core `/v1/auth/*` and `/v1/me` endpoints, plus the Next.js
   login and callback routes and the authenticated server proxy. Replace the
   console's `VITE_RAPHAEL_API_URL` direct calls.
5. **Onboarding UI.** Install app → pick repos → create connector (one-line
   Ignis command) → live connection check (#95, section 3).

## Explicitly out of scope for v1

- Per-tenant BYOK key storage. v1 ships with no external LLM, or with one
  provider configured on the instance.
- Invites, teams and custom roles.
- Postgres and multi-instance core.
- Email or password login.

## Resolved questions

1. **Tenant boundary:** one tenant per GitHub App installation.
2. **Reader role:** non-admin collaborators on an installation get `reader`.
3. **Session lifetime:** seven days, with installation access re-checked on refresh.
