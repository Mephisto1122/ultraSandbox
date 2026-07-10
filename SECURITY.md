# Security model

Ultra-sandbox executes code an AI wrote. That is the point of the tool, so the
design assumes **everything that runs inside a sandbox is untrusted** — including
build scripts, test suites, and anything `exec_command` is asked to run.

## Isolation layers (Docker driver)

Every sandbox container is started with, by default:

| Layer | Flag / mechanism | What it stops |
|---|---|---|
| No network | `--network none` | exfiltration, downloads, C2, cryptomining |
| Dropped capabilities | `--cap-drop ALL` | privilege escalation primitives |
| No setuid escalation | `--security-opt no-new-privileges` | sudo/setuid tricks inside the container |
| Non-root user | baked into every image | root-in-container exploits |
| Immutable rootfs | `--read-only` | tampering with the toolchain image |
| Writable surfaces | one named volume at `/work`, size-capped tmpfs at `/tmp` | confines all writes; caches redirected under `/work` |
| Resource caps | `--memory`, `--cpus`, `--pids-limit` | runaway builds, fork bombs |
| No host mounts | file sync is `docker cp` snapshots | container can never see the host filesystem |
| In-container exec | `exec_command` always runs inside the container | arbitrary commands never touch the host shell |

Network access is **per-sandbox opt-in**: `create_sandbox(..., allow_network=true)`
switches that one container to `bridge`. The server refuses up front when a
toolchain that needs downloads (node, jvm, ruby, php, dotnet, or any `deps`
list) is created without it, so the choice is always explicit and visible in
the tool call.

## Session lifecycle (ephemeral mode)

With `[security].ephemeral = true` (default):

- **Startup**: any `us_*` containers and volumes left by a previous or crashed
  session are force-removed before serving.
- **Exit**: every sandbox created during the session is destroyed
  (`atexit` + SIGTERM/SIGINT handlers). Sandboxes never outlive the session.

Set `ephemeral = false` in `config.toml` only if you deliberately want
long-lived sandboxes with warm caches, and understand the tradeoff.

## Host process

The server itself runs on the host with your user's permissions. Its host-side
surface is deliberately small:

- All local subprocess calls (`docker`, `ssh`, `rsync`) use argv lists — never
  `shell=True`.
- User-controlled strings entering a container shell are `shlex.quote`d.
- `write_files` rejects absolute paths and `..` traversal before staging.
- Staging uses throwaway temp directories.
- The dashboard binds to `127.0.0.1` only and is read-only.
- Logs and state live under `~/.ultra-sandbox`.

## Mac driver

Swift/Xcode builds run on a **remote** EC2 Mac over SSH — nothing executes on
your local machine beyond `ssh`/`rsync` themselves. The remote host is not
containerized (macOS), so treat it as a semi-trusted build machine: use a
dedicated instance, a dedicated SSH key, and don't keep unrelated secrets on it.

## Residual risks (be honest with yourself)

- **Prompt injection → tool calls.** A hostile file or error message could try
  to steer the AI into running something via `exec_command`. It will land
  inside the isolated container, but keep the client's tool-approval prompts ON.
- **Kernel escape.** Containers share the host kernel; a container escape
  0-day defeats these layers. For hostile-by-design workloads, run the whole
  server inside a VM or WSL2.
- **allow_network sandboxes** can reach the internet by definition. Grant it
  only when a build genuinely needs dependency downloads.

## Reporting

Open a GitHub issue (or a private security advisory on the repository) with
reproduction steps.
