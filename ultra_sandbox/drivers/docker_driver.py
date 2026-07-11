"""Docker driver — local containers for every portable toolchain.

Security posture (tight by default, see SECURITY.md):
- **No network**: containers run with `--network none` unless the sandbox was
  created with allow_network=True (needed for toolchains that fetch deps at
  build time, e.g. npm/gradle).
- **Dropped privileges**: `--cap-drop ALL`, `--security-opt no-new-privileges`,
  non-root user baked into every image, `--pids-limit` against fork bombs.
- **Immutable root filesystem**: `--read-only`; only two writable surfaces
  exist — a per-sandbox named volume at /work and a size-capped tmpfs at /tmp.
  HOME and all toolchain caches are redirected into /work.
- **Ephemeral sessions**: with [security].ephemeral (default), every sandbox is
  destroyed when the server exits, and stale `us_*` containers/volumes from
  crashed sessions are reaped at startup.
- **No shell on the host**: every local invocation is an argv list (never
  `shell=True`); user input is quoted with shlex before entering a container
  shell; file paths are validated against traversal before staging.
- exec_command always executes *inside* the container, never on the host.

File sync is `docker cp` snapshots — containers never mount the host
filesystem.
"""

from __future__ import annotations

import shlex
import tempfile
from pathlib import Path

from ..models import RunResult, Sandbox
from .base import Driver, DriverError

IMAGES_DIR = Path(__file__).resolve().parent.parent / "images"

WORKDIR = "/work"
SANDBOX_HOME = "/work/.home"

# PATH fix (see #go/#rust "binary exists but not found"):
# We override HOME to /work/.home so caches persist in the volume. But a *login*
# shell re-sources /etc/profile and can reset PATH, dropping the toolchain dirs
# the base images set via ENV (golang -> /usr/local/go/bin, rust ->
# /usr/local/cargo/bin, etc.). We therefore (a) run commands with `sh -c`, not
# `sh -lc`, and (b) pin an explicit PATH that includes every toolchain bin dir
# plus the user-install bin dir under the new HOME (so `pip install --user`
# tools such as pytest are on PATH).
TOOLCHAIN_PATHS = [
    f"{SANDBOX_HOME}/.local/bin",     # pip --user (pytest, etc.)
    f"{SANDBOX_HOME}/.cargo/bin",     # cargo-installed binaries
    f"{SANDBOX_HOME}/go/bin",         # go install
    "/usr/local/go/bin",              # golang image
    "/usr/local/cargo/bin",           # rust image
    "/usr/local/rustup/bin",
    "/opt/zig", "/opt/kotlinc/bin",   # our custom images
    "/usr/local/sbin", "/usr/local/bin",
    "/usr/sbin", "/usr/bin", "/sbin", "/bin",
]
SANDBOX_PATH = ":".join(TOOLCHAIN_PATHS)

# Toolchain caches redirected under the writable volume so a read-only rootfs
# never breaks a build.
CACHE_ENV = {
    "HOME": SANDBOX_HOME,
    "PATH": SANDBOX_PATH,
    "GOPATH": f"{SANDBOX_HOME}/go",
    "GOCACHE": f"{SANDBOX_HOME}/.cache/go-build",
    "CARGO_HOME": f"{SANDBOX_HOME}/.cargo",
    "npm_config_cache": f"{SANDBOX_HOME}/.npm",
    "GRADLE_USER_HOME": f"{SANDBOX_HOME}/.gradle",
    "PIP_CACHE_DIR": f"{SANDBOX_HOME}/.cache/pip",
    "PYTHONUSERBASE": f"{SANDBOX_HOME}/.local",
    "NUGET_PACKAGES": f"{SANDBOX_HOME}/.nuget",
    "BUNDLE_PATH": f"{SANDBOX_HOME}/.bundle",
    "COMPOSER_HOME": f"{SANDBOX_HOME}/.composer",
    "XDG_CACHE_HOME": f"{SANDBOX_HOME}/.cache",
    "DENO_DIR": f"{SANDBOX_HOME}/.cache/deno",
    "PUB_CACHE": f"{SANDBOX_HOME}/.pub-cache",
    "MIX_HOME": f"{SANDBOX_HOME}/.mix",
    "HEX_HOME": f"{SANDBOX_HOME}/.hex",
    "CABAL_DIR": f"{SANDBOX_HOME}/.cabal",
    "STACK_ROOT": f"{SANDBOX_HOME}/.stack",
    "DOTNET_CLI_HOME": f"{SANDBOX_HOME}/.dotnet",
    "CRYSTAL_CACHE_DIR": f"{SANDBOX_HOME}/.cache/crystal",
    "SWIFTPM_CACHE": f"{SANDBOX_HOME}/.swiftpm",
}

from ..languages import LANGUAGES


def _sub(template: str, **kw) -> str:
    for k, v in kw.items():
        template = template.replace("{" + k + "}", v)
    return template


NETWORK_HUNGRY = {n for n, s in LANGUAGES.items() if s.network_build}


class DockerDriver(Driver):
    name = "docker"

    # ---------- images ----------

    def _image(self, lang: str) -> str:
        return f"{self.config['docker']['image_prefix']}/{lang}"

    def _ensure_image(self, lang: str) -> None:
        image = self._image(lang)
        probe = self._run_local(["docker", "image", "inspect", image], timeout_s=30)
        if probe.exit_code == 0:
            return
        dockerfile_dir = IMAGES_DIR / lang
        if not dockerfile_dir.is_dir():
            raise DriverError(
                f"No Dockerfile for {lang!r} at {dockerfile_dir}. "
                f"Add one (see images/go/Dockerfile as a template)."
            )
        build = self._run_local(
            ["docker", "build", "-t", image, str(dockerfile_dir)],
            timeout_s=1800,
        )
        if build.exit_code != 0:
            raise DriverError(f"docker build for {image} failed:\n{build.stderr[-2000:]}")

    # ---------- lifecycle ----------

    def create(self, sb: Sandbox, deps: list[str] | None, allow_network: bool = False) -> None:
        sec = self.config["security"]
        default_net = sec.get("default_network", "none")
        # Resolve the effective network:
        #   allow_network=True  -> always bridge (explicit request)
        #   allow_network=False -> the configured default (none, or bridge if the
        #                          user opted their whole setup into network-on)
        net_on = allow_network or default_net == "bridge"

        needs_net = bool(deps) or sb.lang in NETWORK_HUNGRY
        if needs_net and not net_on:
            what = "installing `deps`" if deps else f"the standard {sb.lang!r} build"
            raise DriverError(
                f"{what} needs to download from the network (git / package registry), "
                "but this sandbox is isolated. Recreate with allow_network=true (or set "
                "[security].default_network = \"bridge\" to allow downloads by default)."
            )

        self._ensure_image(sb.lang)
        name = f"us_{sb.id}"
        volume = f"us_{sb.id}"
        cfg = self.config["docker"]

        vol = self._run_local(["docker", "volume", "create", volume], timeout_s=30)
        if vol.exit_code != 0:
            raise DriverError(f"docker volume create failed: {vol.stderr.strip()}")

        network = "bridge" if net_on else "none"
        argv = [
            "docker", "run", "-d", "--name", name,
            "--network", network,
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(sec["pids_limit"]),
            "--memory", str(cfg["memory"]), "--cpus", str(cfg["cpus"]),
            "-v", f"{volume}:{WORKDIR}",
        ]
        if sec["read_only_rootfs"]:
            argv += ["--read-only", "--tmpfs", f"/tmp:rw,exec,size={sec['tmpfs_size']}"]
        for k, v in CACHE_ENV.items():
            argv += ["-e", f"{k}={v}"]
        argv += ["-w", WORKDIR, self._image(sb.lang), "sleep", "infinity"]

        run = self._run_local(argv, timeout_s=120)
        if run.exit_code != 0:
            self._run_local(["docker", "volume", "rm", "-f", volume], timeout_s=30)
            raise DriverError(f"docker run failed: {run.stderr.strip()}")

        sb.meta["container"] = name
        sb.meta["volume"] = volume
        sb.meta["network"] = network
        init = self._run_local(
            ["docker", "exec", name, "mkdir", "-p", SANDBOX_HOME], timeout_s=30
        )
        if init.exit_code != 0:
            raise DriverError(f"container init failed: {init.stderr.strip()}")
        if deps:
            installer = _dep_installer(sb.lang, deps)
            if installer:
                self.exec(sb, installer)

    def destroy(self, sb: Sandbox) -> None:
        name = sb.meta.get("container")
        if name:
            self._run_local(["docker", "rm", "-f", name], timeout_s=60)
        volume = sb.meta.get("volume")
        if volume:
            self._run_local(["docker", "volume", "rm", "-f", volume], timeout_s=30)

    def reap_stale(self) -> int:
        """Remove leftover us_* containers/volumes from previous sessions.

        Called at startup in ephemeral mode so a crashed session never leaves
        running containers behind. Returns how many containers were removed.
        """
        ps = self._run_local(
            ["docker", "ps", "-aq", "--filter", "name=us_"], timeout_s=30
        )
        ids = [i for i in ps.stdout.split() if i]
        for cid in ids:
            self._run_local(["docker", "rm", "-f", cid], timeout_s=60)
        vols = self._run_local(
            ["docker", "volume", "ls", "-q", "--filter", "name=us_"], timeout_s=30
        )
        for v in [v for v in vols.stdout.split() if v]:
            self._run_local(["docker", "volume", "rm", "-f", v], timeout_s=30)
        return len(ids)

    # ---------- file sync ----------

    def write_files(self, sb: Sandbox, files: dict[str, str]) -> None:
        name = self._container(sb)
        with tempfile.TemporaryDirectory(prefix="us_stage_") as stage:
            stage_path = Path(stage)
            for rel, content in files.items():
                rel_path = Path(rel)
                if rel_path.is_absolute() or ".." in rel_path.parts:
                    raise DriverError(f"File path must be relative and inside the project: {rel!r}")
                dest = stage_path / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
            cp = self._run_local(
                ["docker", "cp", f"{stage}/.", f"{name}:{WORKDIR}/"], timeout_s=120
            )
            if cp.exit_code != 0:
                raise DriverError(f"docker cp failed: {cp.stderr.strip()}")

    # ---------- execution ----------

    def _container(self, sb: Sandbox) -> str:
        name = sb.meta.get("container")
        if not name:
            raise DriverError("Sandbox has no container (was create_sandbox interrupted?).")
        return name

    def _exec_in(self, sb: Sandbox, shell_cmd: str) -> RunResult:
        # `sh -c`, not `sh -lc`: a login shell re-sources /etc/profile and would
        # reset PATH, losing the toolchain dirs (the go/cargo "not found" bug).
        return self._run_local([
            "docker", "exec", "-w", WORKDIR, self._container(sb),
            "sh", "-c", shell_cmd,
        ])

    def build(self, sb: Sandbox, target: str | None) -> RunResult:
        spec = LANGUAGES.get(sb.lang)
        if spec is None:
            raise DriverError(f"No build command defined for {sb.lang!r}.")
        cmd = spec.build
        if target:
            cmd = f"{cmd} {shlex.quote(target)}"
        return self._exec_in(sb, cmd)

    def test(self, sb: Sandbox, filter: str | None) -> RunResult:
        spec = LANGUAGES.get(sb.lang)
        if spec is None:
            raise DriverError(f"No test command defined for {sb.lang!r}.")
        if filter and spec.test_filter:
            cmd = _sub(spec.test_filter, filter=shlex.quote(filter))
        else:
            cmd = spec.test
        return self._exec_in(sb, cmd)

    def exec(self, sb: Sandbox, cmd: str) -> RunResult:
        # Always inside the container — never on the host.
        return self._exec_in(sb, cmd)


def _dep_installer(lang: str, deps: list[str]) -> str | None:
    spec = LANGUAGES.get(lang)
    if not spec or not spec.dep_add:
        return None
    quoted = " ".join(shlex.quote(d) for d in deps)
    return _sub(spec.dep_add, deps=quoted)
