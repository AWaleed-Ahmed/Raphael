# Raphael IDE (Cursor / VS Code)

**Status:** P0 extension — install via VSIX
**Package:** `raphael.raphael-ide`
**Talks to:** local agent at `http://127.0.0.1:8091` (I0 APIs)
**Never calls:** sandbox controller (`:8090`)

Inspect Raphael runs, apply proposed manifest fixes into your workspace, open the dry-run draft PR URL, and record accept/reject feedback — without leaving Cursor or VS Code.

PRD: [`prd.md`](prd.md) · Agent I0: [`../prd-i0-api.md`](../prd-i0-api.md)

---

## Install from this GitHub repo

### Option A — Install a release VSIX (partners)

1. Open the repo on GitHub → **Releases** → download `raphael-ide-*.vsix` (when attached to a release such as `ide-v0.1.0`).
2. In **Cursor** or **VS Code**: Extensions view → `⋯` → **Install from VSIX…** → select the file.
3. Reload the window if prompted.

### Option B — Build from source (maintainers / contributors)

```bash
git clone https://github.com/AWaleed-Ahmed/Raphael.git
cd Raphael/interface/IDE
npm install
npm run compile
npx @vscode/vsce package --no-dependencies
# → raphael-ide-0.2.0.vsix
```

Then **Install from VSIX…** as above.

```bash
npm run test:unit   # path-guard / delivery_plan unit tests
```

---

## Prerequisites

1. **Open the app workspace** in Cursor (the repo that contains manifests you will patch — e.g. a checkout that includes `deploy/`).
   For the demo scenario, open
   `Raphael/agent/fixtures/scenarios/probe_port_mismatch`
   (or the monorepo root if that folder is reachable as a relative path from the agent run).

2. **Start the Raphael agent** (from a Raphael clone):

```bash
cd agent
source .venv/bin/activate   # or your venv
export RAPHAEL_PARTNER_MODE=dry_run
export RAPHAEL_PUBLISH_MODE=dry_run
export RAPHAEL_LLM_DIAGNOSIS=0
export RAPHAEL_AGENT_LISTEN=127.0.0.1:8091
# optional: export RAPHAEL_INTERFACE_TOKEN=secret
raphael-agent-serve
```

3. Extension settings (Cursor/VS Code Settings UI or `settings.json`):

| Setting | Default | Meaning |
|---------|---------|---------|
| `raphael.agentBaseUrl` | `http://127.0.0.1:8091` | Agent HTTP root |
| API token | SecretStorage via **Raphael: Set API Token** | Only if agent has `RAPHAEL_INTERFACE_TOKEN` |

---

## Day-one walkthrough

Use the **sidebar** (activity-bar angel-wings icon). You should not need the Command Palette for normal work.

### 1. Open Raphael

Click the **Raphael** icon (angel wings with **+**) in the Activity Bar. The panel has three tabs:

| Tab | What it does |
|-----|----------------|
| **How to use** | In-extension docs, Test connection, Set API token |
| **Runs** | Live list of agent runs — click one to select |
| **Actions** | Apply Fix, Open Draft PR, Feedback, Open details |

Status at the top shows Connected / Offline. Use **↻** or **Refresh runs** to reload.

### 2. Create a demo run (agent must be up)

```bash
export WS="/path/to/Raphael/agent/fixtures/scenarios/probe_port_mismatch"
curl -sS -X POST "http://127.0.0.1:8091/v1/runs" \
  -H "Content-Type: application/json" \
  -d "{
    \"trigger_kind\": \"manual_ui\",
    \"action_id\": \"ide-demo-1\",
    \"repository\": {\"owner\": \"raphael\", \"name\": \"demo\"},
    \"commit_sha\": \"abcdef1234567\",
    \"workspace_path\": \"$WS\",
    \"manifests\": {
      \"type\": \"yaml\",
      \"path\": \"deploy/manifests\",
      \"fixed_path\": \"deploy/manifests_fixed\"
    },
    \"sandbox_mode\": \"recorded_stub\"
  }"
```

Expect `status=success_draft_pr_ready` and a `run_id`.

### 3. Click through the UI

1. **How to use** → **Test connection** (status bar / panel should show Connected).
2. **Runs** → **Refresh runs** → click your run (opens **Actions**).
3. **Actions** → **Apply fix to workspace** → confirm → check allowlisted files (e.g. `deploy/…`).
4. **Open draft PR** → browser opens the dry-run compare URL.
5. **Feedback: accepted** or **rejected**.

---

## Commands (optional)

Palette commands still exist as a fallback (`Raphael: …`). Prefer the sidebar tabs for day-to-day use.

There is **no** Merge command.

---

## Safety

- Paths must stay inside the workspace and under `fix_rules.writable_path_prefixes` (fallback: `deploy/`, `k8s/`, `manifests/`, …).
- `..` and absolute escapes are rejected.
- Extension never calls `RAPHAEL_SANDBOX_URL`.
- Dry-run publish remains the agent’s responsibility (`RAPHAEL_PARTNER_MODE`).

---

## Publishing a VSIX on GitHub Releases

```bash
cd interface/IDE && npm run compile && npx @vscode/vsce package --no-dependencies
gh release create ide-v0.2.0 ./raphael-ide-0.2.0.vsix \
  --title "Raphael IDE 0.2.0" \
  --notes "P0: runs panel, apply fix, draft PR link, feedback."
```

(Requires `gh` auth on the `AWaleed-Ahmed/Raphael` repo.)

---

## Development

```bash
npm install
npm run compile   # out/
npm run watch
npm run test:unit
```

Press F5 in VS Code/Cursor against this folder only if you add an Extension Development Host launch config; otherwise compile + Install from VSIX is enough for pilots.
