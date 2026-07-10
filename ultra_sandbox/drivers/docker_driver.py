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

# Toolchain caches redirected under the writable volume so a read-only rootfs
# never breaks a build.
CACHE_ENV = {
    "HOME": SANDBOX_HOME,
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
}

BUILD_CMDS: dict[str, str] = {
    "go":     "go build ./...",
    "cpp":    "cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug && cmake --build build -j",
    "node":   "npm install --no-audit --no-fund && npm run build --if-present",
    "python": "if [ -f requirements.txt ]; then pip install --user -q -r requirements.txt; fi; "
              "if [ -f pyproject.toml ]; then pip install --user -q -e . || true; fi; "
              "python -m compileall -q .",
    "rust":   "cargo build",
    "jvm":    "gradle --no-daemon assemble",
    "ruby":   "if [ -f Gemfile ]; then bundle install --quiet; fi; ruby -c $(find . -name '*.rb' | head -50)",
    "php":    "if [ -f composer.json ]; then composer install --quiet; fi; "
              "for f in $(find . -name '*.php'); do php -l \"$f\" || exit 1; done",
    "dotnet": "dotnet build",
}

TEST_CMDS: dict[str, str] = {
    "go":     "go test ./...",
    "cpp":    "ctest --test-dir build --output-on-failure",
    "node":   "npm test --silent",
    "python": "python -m pytest -q",
    "rust":   "cargo test",
    "jvm":    "gradle --no-daemon test",
    "ruby":   "if [ -f Rakefile ]; then rake test; else ruby -Itest test/*_test.rb; fi",
    "php":    "./vendor/bin/phpunit || phpunit",
    "dotnet": "dotnet test",
}

TEST_FILTER_CMDS: dict[str, str] = {
    "go":     "go test ./... -run {f}",
    "cpp":    "ctest --test-dir build --output-on-failure -R {f}",
    "node":   "npm test --silent -- {f}",
    "python": "python -m pytest -q -k {f}",
    "rust":   "cargo test {f}",
    "jvm":    "gradle --no-daemon test --tests {f}",
    "dotnet": "dotnet test --filter {f}",
}

# Languages whose *standard build command* needs the network (dep fetch at
# build time). Used only to produce a clearer error message up front.
NETWORK_HUNGRY = {"node", "jvm", "ruby", "php", "dotnet"}


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
        if deps and not allow_network and sec["network"] == "none":
            raise DriverError(
                "This sandbox has no network (security default), so `deps` cannot be "
                "installed. Recreate with allow_network=true if dependency downloads "
                "are needed."
            )
        if sb.lang in NETWORK_HUNGRY and not allow_network and sec["network"] == "none":
            raise DriverError(
                f"The standard {sb.lang!r} build fetches dependencies from the network, "
                "but sandboxes are network-isolated by default. Recreate with "
                "allow_network=true to permit outbound access for this sandbox only."
            )

        self._ensure_image(sb.lang)
        name = f"us_{sb.id}"
        volume = f"us_{sb.id}"
        cfg = self.config["docker"]

        vol = self._run_local(["docker", "volume", "create", volume], timeout_s=30)
        if vol.exit_code != 0:
            raise DriverError(f"docker volume create failed: {vol.stderr.strip()}")

        network = "bridge" if allow_network else sec["network"]
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
        return self._run_local([
            "docker", "exec", "-w", WORKDIR, self._container(sb),
            "sh", "-lc", shell_cmd,
        ])

    def build(self, sb: Sandbox, target: str | None) -> RunResult:
        cmd = BUILD_CMDS.get(sb.lang)
        if cmd is None:
            raise DriverError(f"No build command defined for {sb.lang!r}.")
        if target and sb.lang not in ("go", "cpp"):
            cmd = f"{cmd} {shlex.quote(target)}"
        return self._exec_in(sb, cmd)

    def test(self, sb: Sandbox, filter: str | None) -> RunResult:
        if filter:
            tmpl = TEST_FILTER_CMDS.get(sb.lang)
            cmd = tmpl.format(f=shlex.quote(filter)) if tmpl else TEST_CMDS[sb.lang]
        else:
            cmd = TEST_CMDS.get(sb.lang)
        if cmd is None:
            raise DriverError(f"No test command defined for {sb.lang!r}.")
        return self._exec_in(sb, cmd)

    def exec(self, sb: Sandbox, cmd: str) -> RunResult:
        # Always inside the container — never on the host.
        return self._exec_in(sb, cmd)


def _dep_installer(lang: str, deps: list[str]) -> str | None:
    quoted = " ".join(shlex.quote(d) for d in deps)
    return {
        "go":     f"go get {quoted}",
        "node":   f"npm install --no-audit --no-fund {quoted}",
        "python": f"pip install --user -q {quoted}",
        "rust":   f"cargo add {quoted}",
        "ruby":   f"gem install {quoted}",
        "php":    f"composer require {quoted}",
        "dotnet": " && ".join(f"dotnet add package {shlex.quote(d)}" for d in deps),
    }.get(lang)
