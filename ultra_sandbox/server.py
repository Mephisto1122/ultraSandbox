"""The MCP server — the exact tool contract from the build plan.

Repair-loop contract: Claude drives the loop (write → build → read stderr →
patch → repeat); the server keeps score. Every run_build / run_tests response
carries `repair_attempts` and `max_attempts`, and once the cap is reached the
response says so explicitly — "gave up after N attempts" is a real outcome the
dashboard shows, never a silent failure.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .cost import MacHostClock
from .docs_search import DocsSearch
from .drivers import DriverError, Router
from .models import (
    STATUS_BUILDING, STATUS_DESTROYED, STATUS_TESTING,
    DOCKER_LANGS, MAC_LANGS, Sandbox,
)
from .state import State

config = load_config()
state = State(config)
router = Router(config)
docs = DocsSearch(config)
mac_clock = MacHostClock(config)

MAX_ATTEMPTS = int(config["server"]["max_attempts"])

mcp = FastMCP("ultra-sandbox")


def _loop_status(sb: Sandbox) -> dict:
    out = {"repair_attempts": sb.repair_attempts, "max_attempts": MAX_ATTEMPTS}
    if sb.repair_attempts >= MAX_ATTEMPTS:
        out["give_up"] = (
            f"Repair loop cap reached ({sb.repair_attempts}/{MAX_ATTEMPTS} failed rounds). "
            "Stop patching: report the last error to the user as the outcome, along with "
            "what was tried. Do not keep iterating."
        )
    return out


def _err(e: Exception) -> dict:
    return {"error": str(e)}


@mcp.tool()
def create_sandbox(project_id: str, lang: str, deps: list[str] | None = None,
                   allow_network: bool = False) -> dict:
    """Create a session-scoped, isolated sandbox for a project.

    Docker languages (local containers): go, c, cpp, rust, zig, haskell, crystal,
    swiftpm, python, node, typescript, deno, ruby, php, perl, lua, elixir, jvm,
    kotlin, scala, dotnet, dart. Mac languages (remote EC2 Mac over SSH): swift,
    xcodeproj, objc.

    Network: sandboxes are isolated by default. **Pass allow_network=true whenever
    the project needs to reach the internet** — cloning a git repo, or installing
    libraries (pip/npm/cargo/go get/gem/composer/mix/gradle/dotnet restore, and
    any git-based dependency). git is preinstalled in every image. Toolchains
    whose standard build downloads dependencies (rust, node, jvm, and others) are
    refused without it, with a clear message. Leave it false only for
    self-contained code that needs no downloads.

    Security when network is on: the container still runs with dropped
    capabilities, no-new-privileges, a read-only root filesystem, and resource
    limits — network access widens only outbound reachability. Returns sandbox_id.
    """
    try:
        driver_name, driver = router.for_lang(lang)
    except ValueError as e:
        return _err(e)
    sb = Sandbox(project_id=project_id, lang=lang.lower(), driver=driver_name)
    try:
        driver.create(sb, deps, allow_network=allow_network)
    except DriverError as e:
        return _err(e)
    if driver_name == "mac":
        mac_clock.mark_allocated()
    state.add(sb)
    return {
        "sandbox_id": sb.id,
        "driver": driver_name,
        "network": sb.meta.get("network", "remote" if driver_name == "mac" else "none"),
        "note": ("Runs on the remote Mac host — remember it bills in 24h blocks."
                 if driver_name == "mac" else
                 "Isolated local container (session-scoped; destroyed on exit)."),
    }


@mcp.tool()
def write_files(sandbox_id: str, files: dict[str, str]) -> dict:
    """Write files into the sandbox. `files` maps relative paths to full file
    contents (whole files, not diffs). Existing files at the same paths are
    overwritten; other files are left alone, so incremental patching works.
    """
    try:
        sb = state.get(sandbox_id)
        router.by_name(sb.driver).write_files(sb, files)
    except (KeyError, DriverError) as e:
        return _err(e)
    state.update(sb)
    return {"ok": True, "files_written": sorted(files.keys())}


@mcp.tool()
def run_build(sandbox_id: str, target: str | None = None) -> dict:
    """Build the project with the toolchain's native command (go build ./...,
    cmake --build, cargo build, xcodebuild build, ...). For xcodeproj/objc,
    `target` is the Xcode scheme. Nonzero exit_code means read stderr, patch
    with write_files, and build again — until it's green or max_attempts is hit.
    """
    try:
        sb = state.get(sandbox_id)
    except KeyError as e:
        return _err(e)
    state.update(sb, status=STATUS_BUILDING)
    try:
        result = router.by_name(sb.driver).build(sb, target)
    except DriverError as e:
        state.update(sb, status="failing")
        return _err(e)
    result.log_path = state.append_log(sb, "build", result, header=f"run_build target={target}")
    state.record_run(sb, "build", result)
    return {**result.to_dict(), **_loop_status(sb)}


@mcp.tool()
def run_tests(sandbox_id: str, filter: str | None = None) -> dict:
    """Run the test suite (go test ./..., pytest, cargo test, swift test,
    xcodebuild test, ...). `filter` narrows to matching tests — for
    xcodeproj/objc it is the required Xcode scheme name. Nonzero exit_code
    means read the failing output, patch, and re-run.
    """
    try:
        sb = state.get(sandbox_id)
    except KeyError as e:
        return _err(e)
    state.update(sb, status=STATUS_TESTING)
    try:
        result = router.by_name(sb.driver).test(sb, filter)
    except DriverError as e:
        state.update(sb, status="failing")
        return _err(e)
    result.log_path = state.append_log(sb, "test", result, header=f"run_tests filter={filter}")
    state.record_run(sb, "test", result)
    return {**result.to_dict(), **_loop_status(sb)}


@mcp.tool()
def exec_command(sandbox_id: str, cmd: str) -> dict:
    """Run an arbitrary shell command inside the sandbox (inspect files, run a
    binary, check a version). Use run_build/run_tests for builds and tests so
    the repair-loop trace stays accurate.
    """
    try:
        sb = state.get(sandbox_id)
        result = router.by_name(sb.driver).exec(sb, cmd)
    except (KeyError, DriverError) as e:
        return _err(e)
    result.log_path = state.append_log(sb, "exec", result, header=f"exec {cmd[:80]}")
    state.record_run(sb, "exec", result)
    return result.to_dict()


@mcp.tool()
def get_logs(sandbox_id: str, since: int | None = None, kind: str | None = None) -> dict:
    """Read captured logs for a sandbox. `kind` is build|test|exec (default:
    all); `since` is a line offset — pass the previous total_lines to tail only
    new output.
    """
    try:
        sb = state.get(sandbox_id)
    except KeyError as e:
        return _err(e)
    return {"logs": state.read_logs(sb, kind=kind, since_line=since or 0)}


@mcp.tool()
def search_docs(query: str, lang: str | None = None) -> dict:
    """Search current, first-party framework/language documentation. Use this
    instead of memory whenever a build error involves an API signature, a
    deprecation, a CMake policy, a SwiftUI modifier, etc. Results are short
    snippets with source URLs (allowlisted doc domains only) — fetch nothing
    else; paraphrase, don't copy. Cached per session.
    """
    return docs.search(query, lang)


@mcp.tool()
def destroy_sandbox(sandbox_id: str) -> dict:
    """Tear down a sandbox: removes the Docker container or the remote working
    directory. (Never releases the Mac dedicated host itself — that's a
    deliberate human action because of 24h-block billing.)
    """
    try:
        sb = state.get(sandbox_id)
        router.by_name(sb.driver).destroy(sb)
    except (KeyError, DriverError) as e:
        return _err(e)
    state.update(sb, status=STATUS_DESTROYED)
    return {"ok": True}


@mcp.tool()
def list_sandboxes() -> dict:
    """List all sandboxes with language, driver, status, repair-loop trace
    length, and a cost estimate (Docker = 0; Mac = the shared host clock).
    """
    mac = mac_clock.summary()
    items = []
    for sb in state.all():
        items.append({
            "id": sb.id,
            "project_id": sb.project_id,
            "lang": sb.lang,
            "driver": sb.driver,
            "status": sb.status,
            "repair_attempts": sb.repair_attempts,
            "max_attempts": MAX_ATTEMPTS,
            "last_log_line": sb.last_log_line,
            "cost_estimate": 0.0 if sb.driver == "docker" else mac.get("estimated_cost_usd"),
        })
    return {"sandboxes": items, "mac_host": mac}


# ---------------------------------------------------------------------------
# Session lifecycle (ephemeral security mode)
# ---------------------------------------------------------------------------

def reap_previous_sessions() -> None:
    """Startup: remove stale us_* containers/volumes left by crashed sessions."""
    if not config["security"]["ephemeral"]:
        return
    try:
        from .drivers.docker_driver import DockerDriver
        driver = router.by_name("docker")
        if isinstance(driver, DockerDriver):
            driver.reap_stale()
    except Exception:
        # Docker not installed / not running: nothing to reap.
        pass


def shutdown_all() -> None:
    """Exit: destroy every sandbox created in this session."""
    if not config["security"]["ephemeral"]:
        return
    for sb in state.all(include_destroyed=False):
        try:
            router.by_name(sb.driver).destroy(sb)
        except Exception:
            pass
        try:
            state.update(sb, status=STATUS_DESTROYED)
        except Exception:
            pass
