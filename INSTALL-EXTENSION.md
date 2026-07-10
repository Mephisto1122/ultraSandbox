# Installing ultra-sandbox as a Desktop Extension (.mcpb)

This is the one-click install path — no editing `claude_desktop_config.json` by hand.
Your `BRAVE_API_KEY` gets stored in the OS keychain (Windows Credential Manager) instead
of plaintext, and the config path / dashboard port become form fields in Claude Desktop.

## What's in the box

- `manifest.json` — declares the server, its 9 tools, and 3 optional config fields
  (config file, Brave API key, dashboard port). Uses `"type": "uv"` so the host installs
  Python dependencies (including pydantic, which the MCP SDK needs and which can't be
  portably bundled the old Python way).
- `.mcpbignore` — keeps your venv, `config.toml`, local state, and caches out of the bundle.

## Prerequisites

- Claude Desktop (latest version)
- [`uv`](https://docs.astral.sh/uv/) on PATH — the `uv` bundle type uses it to install deps.
  On Windows: `winget install astral-sh.uv` (then reopen your terminal).
- Docker Desktop running (for the local build sandboxes)
- The MCPB CLI to build the bundle: `npm install -g @anthropic-ai/mcpb`

## Build the .mcpb

From the project root (the folder with `manifest.json`):

```powershell
mcpb validate .        # sanity-check the manifest
mcpb pack .            # produces ultra-sandbox.mcpb
```

`mcpb pack` reads `.mcpbignore`, bundles the source + manifest, and validates as it goes.

## Install it

1. Open Claude Desktop → **Settings → Extensions**.
2. Click **Advanced settings**, then **Install Extension…** (add custom) — or just
   drag `ultra-sandbox.mcpb` straight onto the Settings window.
3. Select the `ultra-sandbox.mcpb` file. In the review dialog you'll see the extension
   name, description, and its tools. Fill in the optional fields:
   - **Config file** — point at your `config.toml` if you edited one (needed before the Mac
     driver works). Leave blank to use defaults.
   - **Brave Search API key** — paste it to enable `search_docs`. Stored in the keychain.
   - **Dashboard port** — defaults to 8787.
4. Install. The tools are available in new conversations immediately; the dashboard comes
   up at `http://localhost:<port>`.

## Verify

Click the **"+"** in the chat box → **Connectors** to see ultra-sandbox and its tools, or
open Developer settings to check connection status and logs. Then ask Claude to create a Go
sandbox and build something — that first end-to-end build is the real test.

## Updating

Rebuild with a bumped `version` in `manifest.json` and reinstall the new `.mcpb`. Privately
distributed extensions don't auto-update, so you install the new file manually.

## Note on the two install methods

- **Desktop Extension (.mcpb)** — this file. Best for Claude Desktop; keychain secrets,
  form-based config, easy updates.
- **Manual `claude_desktop_config.json` / Claude Code `.mcp.json`** — see the main README.
  Still valid, and what you'll use for Claude Code specifically. Both run the exact same
  local stdio server.

Do **not** use the "Add custom connector" URL flow for this — that path reaches your server
from Anthropic's cloud over the public internet, which a local Docker/SSH tool can't and
shouldn't use.
