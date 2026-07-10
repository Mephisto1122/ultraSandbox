<div align="center">

# 🧰 ultra-sandbox

**Real build-and-run sandboxes for Claude — every language, plus Xcode on a remote AWS Mac, with a live dashboard.**

[![CI](https://github.com/mephisto1122/ultra-sandbox/actions/workflows/ci.yml/badge.svg)](https://github.com/mephisto1122/ultra-sandbox/actions/workflows/ci.yml)
[![22 languages](https://img.shields.io/badge/languages-22-3776AB)](LANGUAGES.md)
[![Docker](https://img.shields.io/badge/local-Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![MCP](https://img.shields.io/badge/protocol-MCP-555555)](https://modelcontextprotocol.io/)
[![AWS EC2 Mac](https://img.shields.io/badge/Xcode-EC2%20Mac-FF9900?logo=amazonwebservices&logoColor=white)](https://aws.amazon.com/ec2/instance-types/mac/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Out of the box, Claude can't compile Go, run your pytest suite, or touch Xcode.
ultra-sandbox gives it all of that: an MCP server where Claude **creates a sandbox,
writes code, builds it, runs the tests, reads the real logs, and patches until green** —
across 22 languages locally and Swift/Xcode on a remote Apple machine.

</div>

---

## What it gives Claude

**22 languages, each in its own toolchain container:**

<div align="center">

![Go](https://img.shields.io/badge/Go-00ADD8?logo=go&logoColor=white)
![C](https://img.shields.io/badge/C-A8B9CC?logo=c&logoColor=black)
![C++](https://img.shields.io/badge/C%2B%2B-00599C?logo=cplusplus&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-000000?logo=rust&logoColor=white)
![Zig](https://img.shields.io/badge/Zig-F7A41D?logo=zig&logoColor=white)
![Haskell](https://img.shields.io/badge/Haskell-5D4F85?logo=haskell&logoColor=white)
![Crystal](https://img.shields.io/badge/Crystal-000000?logo=crystal&logoColor=white)
![Swift](https://img.shields.io/badge/Swift-F05138?logo=swift&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-5FA04E?logo=nodedotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![Deno](https://img.shields.io/badge/Deno-70FFAF?logo=deno&logoColor=black)
![Ruby](https://img.shields.io/badge/Ruby-CC342D?logo=ruby&logoColor=white)
![PHP](https://img.shields.io/badge/PHP-777BB4?logo=php&logoColor=white)
![Perl](https://img.shields.io/badge/Perl-39457E?logo=perl&logoColor=white)
![Lua](https://img.shields.io/badge/Lua-2C2D72?logo=lua&logoColor=white)
![Elixir](https://img.shields.io/badge/Elixir-4B275F?logo=elixir&logoColor=white)
![JVM](https://img.shields.io/badge/JVM-437291?logo=openjdk&logoColor=white)
![Kotlin](https://img.shields.io/badge/Kotlin-7F52FF?logo=kotlin&logoColor=white)
![Scala](https://img.shields.io/badge/Scala-DC322F?logo=scala&logoColor=white)
![.NET](https://img.shields.io/badge/.NET-512BD4?logo=dotnet&logoColor=white)
![Dart](https://img.shields.io/badge/Dart-0175C2?logo=dart&logoColor=white)

</div>

**Plus Xcode / Swift on a remote AWS Mac** — the one thing that can't run in a Linux container:

[![Xcode](https://img.shields.io/badge/Xcode-147EFB?logo=xcode&logoColor=white)](https://developer.apple.com/xcode/)
[![Swift](https://img.shields.io/badge/Swift-F05138?logo=swift&logoColor=white)](https://swift.org/)
[![AWS EC2 Mac](https://img.shields.io/badge/EC2%20Mac-FF9900?logo=amazonec2&logoColor=white)](https://aws.amazon.com/ec2/instance-types/mac/)

`swift` · `xcodeproj` · `objc` built over SSH on an EC2 Mac dedicated host.

**And the machinery that makes it a loop, not a one-shot:**

| Capability | What it does |
|---|---|
| **Repair loop** | build → read stderr → patch → rebuild, until green or a hard cap says "gave up" — loudly, never silently |
| **Docs search** | pulls current first-party docs mid-loop, so Claude checks the real API instead of guessing |
| **Live dashboard** | `localhost:8787` — every sandbox, its status, logs, the repair-loop trace, and the Mac-host cost clock |

Each sandbox spins up per session and is torn down when you're done. It runs on your
machine with sensible isolation (network-off by default, dropped privileges, read-only
rootfs) so you can actually trust it — details in [SECURITY.md](SECURITY.md), but the
point of the tool is the capability above, not the sandboxing.

## Under the hood

Every sandbox container starts with **no network** (opt in per sandbox with
`allow_network`), `--cap-drop ALL`, `no-new-privileges`, a **read-only root filesystem**
(only a per-sandbox volume at `/work` and a capped tmpfs at `/tmp` are writable), a
non-root user, memory/CPU/PID
limits, and **no host mounts** (file sync is `docker cp` snapshots). `exec_command`
always executes *inside* the container.

Sandboxes are **session-scoped**: stale containers from crashed sessions are reaped at
startup, and everything is destroyed when the server exits.

Network is per-sandbox **opt-in** — `create_sandbox(..., allow_network=true)` — and the
server refuses up front when a toolchain that needs downloads is created without it,
so the choice is always explicit.

Full threat model: [SECURITY.md](SECURITY.md).

## Install

**Prerequisites:** Docker Desktop running, plus [`uv`](https://docs.astral.sh/uv/)
on your PATH (the extension uses it to install Python deps). On Windows:
`winget install astral-sh.uv`.

### Recommended: one-click Desktop Extension (`.mcpb`)

Build the bundle once:

```bash
npm install -g @anthropic-ai/mcpb
git clone https://github.com/mephisto1122/ultra-sandbox.git
cd ultra-sandbox
mcpb pack .          # produces ultra-sandbox.mcpb
```

Then in Claude Desktop: **Settings → Extensions → Advanced settings →
Install Extension…**, and select `ultra-sandbox.mcpb` (or just drag the file
onto the Settings window). Fill in the optional fields — config path, Brave API
key (stored in your OS keychain), dashboard port — and install. Details:
[INSTALL-EXTENSION.md](INSTALL-EXTENSION.md).

> Use the **Extensions** page, not "Add custom connector." Custom connectors are
> for *remote* servers reached from Anthropic's cloud; ultra-sandbox is local
> and drives your own Docker/SSH, so it installs as a Desktop Extension.

### Alternative: config file (Claude Code, or if you skip the bundle)

```bash
git clone https://github.com/mephisto1122/ultra-sandbox.git
cd ultra-sandbox
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
cp config.example.toml config.toml
```

Add to `claude_desktop_config.json` (Claude Desktop) or `.mcp.json` (Claude Code):

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
pytest -q          # 41 tests: hardening flags, per-language dispatch, repair loop
```

CI (GitHub Actions) runs the suite on Python 3.11–3.13 and builds all six toolchain
images. Layout, design decisions, and the roadmap live in the docs:
[SECURITY.md](SECURITY.md) · [INSTALL-EXTENSION.md](INSTALL-EXTENSION.md) ·
[config.example.toml](config.example.toml).

## License

[MIT](LICENSE)
