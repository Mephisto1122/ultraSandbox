<div align="center">

# 🛡️ ultra-sandbox

**A hardened, session-scoped build → test → repair sandbox for Claude, over MCP.**

[![CI](https://github.com/YOUR_USERNAME/ultra-sandbox/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/ultra-sandbox/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/isolation-Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![MCP](https://img.shields.io/badge/protocol-MCP-000000?logo=anthropic&logoColor=white)](https://modelcontextprotocol.io/)
[![AWS EC2 Mac](https://img.shields.io/badge/Xcode%20builds-EC2%20Mac-FF9900?logo=amazonwebservices&logoColor=white)](https://aws.amazon.com/ec2/instance-types/mac/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Claude writes code → the sandbox builds and tests it in a locked-down container →
structured logs come back → Claude patches → repeat until green, or a hard cap says
**"gave up"** — loudly, never silently.

</div>

---

## Why

Letting an AI compile and run code on your machine is useful and scary. ultra-sandbox
makes the useful part easy and the scary part small: every build runs inside a
network-less, capability-dropped, read-only-rootfs Docker container that exists only
for the current session.

| | |
|---|---|
| 🐳 **Docker driver** (local) | go · cpp · node · python · rust · jvm · ruby · php · dotnet |
| 🍎 **SSH-Mac driver** (remote EC2 Mac) | swift (SwiftPM) · xcodeproj · objc |
| 📚 **Docs search** | allowlisted first-party documentation, cached per session |
| 📊 **Dashboard** | `localhost:8787` — sandboxes, logs, repair-loop trace, Mac cost clock |

## Security, by default

Every sandbox container starts with **no network**, `--cap-drop ALL`,
`no-new-privileges`, a **read-only root filesystem** (only a per-sandbox volume at
`/work` and a capped tmpfs at `/tmp` are writable), a non-root user, memory/CPU/PID
limits, and **no host mounts** (file sync is `docker cp` snapshots). `exec_command`
always executes *inside* the container.

Sandboxes are **session-scoped**: stale containers from crashed sessions are reaped at
startup, and everything is destroyed when the server exits.

Network is per-sandbox **opt-in** — `create_sandbox(..., allow_network=true)` — and the
server refuses up front when a toolchain that needs downloads is created without it,
so the choice is always explicit.

Full threat model: [SECURITY.md](SECURITY.md).

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/ultra-sandbox.git
cd ultra-sandbox
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
cp config.example.toml config.toml
```

Register with your MCP client:

**Claude Desktop** (`claude_desktop_config.json`, or package as a Desktop Extension —
see [INSTALL-EXTENSION.md](INSTALL-EXTENSION.md)):

```json
{
  "mcpServers": {
    "ultra-sandbox": {
      "command": "/abs/path/.venv/bin/python",
      "args": ["-m", "ultra_sandbox"],
      "env": { "ULTRA_SANDBOX_CONFIG": "/abs/path/config.toml" }
    }
  }
}
```

**Claude Code** (`.mcp.json` in your project, same block).

On first launch the dashboard comes up at **http://localhost:8787**; toolchain images
build lazily on first use.

## Tool surface

```
create_sandbox(project_id, lang, deps?, allow_network?) -> sandbox_id
write_files(sandbox_id, files)                          -> ok
run_build(sandbox_id, target?)   -> {exit_code, stdout, stderr, log_path, duration_ms,
                                     repair_attempts, max_attempts}
run_tests(sandbox_id, filter?)   -> same shape
exec_command(sandbox_id, cmd)    -> runs INSIDE the container
get_logs(sandbox_id, since?, kind?)
search_docs(query, lang?)        -> allowlisted doc snippets + source URLs
destroy_sandbox(sandbox_id)
list_sandboxes()                 -> sandboxes + Mac host cost summary
```

The repair loop is driven by the model and scored by the server: every build/test
result carries `repair_attempts / max_attempts` (default cap 8), and hitting the cap
returns an explicit `give_up` instruction that the dashboard mirrors as a banner.

## The Mac driver and money 💸

Xcode only runs on Apple hardware, so Swift/ObjC builds go over SSH to an
**EC2 Mac dedicated host** you allocate deliberately. AWS bills those hosts in
**24-hour minimum blocks**, so the server never allocates or releases the host
itself — the dashboard just tracks the clock and shows *"Xh remaining in current
block"* against your configured hourly rate.

## Development

```bash
pip install -e ".[dev]"
pytest -q          # 14 tests, including one that asserts every hardening flag
```

CI (GitHub Actions) runs the suite on Python 3.11–3.13 and builds all six toolchain
images. Layout, design decisions, and the roadmap live in the docs:
[SECURITY.md](SECURITY.md) · [INSTALL-EXTENSION.md](INSTALL-EXTENSION.md) ·
[config.example.toml](config.example.toml).

## License

[MIT](LICENSE)
