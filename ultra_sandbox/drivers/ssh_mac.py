"""SSH-Mac driver — Xcode/Swift/iOS on a remote EC2 Mac dedicated host.

No Docker here: macOS toolchains only run on Apple hardware, so this driver is
plain SSH + rsync against a host you've allocated (mac2.metal / mac1.metal).

Language mapping:
- "swift"     → Swift Package Manager (`swift build` / `swift test`)
- "xcodeproj" → xcodebuild against a project/workspace (`target` = scheme)
- "objc"      → same as xcodeproj (ObjC lives in Xcode projects in practice)

Cost note baked into the design: the dedicated host bills in 24-hour minimum
blocks, so create/destroy here never allocates or releases the host itself —
it only makes/removes a working directory. Host allocation stays a deliberate
human action; cost.py just tracks the clock.
"""

from __future__ import annotations

import shlex
import tempfile
from pathlib import Path

from ..models import RunResult, Sandbox
from .base import Driver, DriverError

XCODE_LANGS = {"xcodeproj", "objc"}


class SshMacDriver(Driver):
    name = "mac"

    # ---------- plumbing ----------

    def _conn(self) -> tuple[str, str, list[str]]:
        cfg = self.config["mac"]
        host = cfg["host"].strip()
        if not host:
            raise DriverError(
                "No Mac host configured. Allocate an EC2 Mac dedicated host, start an "
                "instance on it, and set [mac].host in config.toml. Reminder: AWS bills "
                "the dedicated host in 24-hour minimum blocks."
            )
        key = str(Path(cfg["key"]).expanduser())
        target = f"{cfg['user']}@{host}"
        ssh_opts = ["-i", key, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
        return target, key, ssh_opts

    def _ssh(self, remote_cmd: str, timeout_s: int | None = None) -> RunResult:
        target, _key, opts = self._conn()
        return self._run_local(["ssh", *opts, target, remote_cmd], timeout_s=timeout_s)

    def _remote_dir(self, sb: Sandbox) -> str:
        return f"{self.config['mac']['remote_root']}/{sb.id}"

    # ---------- lifecycle ----------

    def create(self, sb: Sandbox, deps: list[str] | None, allow_network: bool = False) -> None:
        rdir = self._remote_dir(sb)
        res = self._ssh(f"mkdir -p {shlex.quote(rdir)} && sw_vers -productVersion", timeout_s=60)
        if res.exit_code != 0:
            raise DriverError(
                f"Could not reach the Mac host over SSH: {res.stderr.strip() or res.stdout.strip()}"
            )
        sb.meta["remote_dir"] = rdir
        sb.meta["macos_version"] = res.stdout.strip()

    def destroy(self, sb: Sandbox) -> None:
        rdir = sb.meta.get("remote_dir")
        if rdir:
            self._ssh(f"rm -rf {shlex.quote(rdir)}", timeout_s=120)

    # ---------- file sync ----------

    def write_files(self, sb: Sandbox, files: dict[str, str]) -> None:
        target, key, _opts = self._conn()
        rdir = self._remote_dir(sb)
        with tempfile.TemporaryDirectory(prefix="us_stage_") as stage:
            stage_path = Path(stage)
            for rel, content in files.items():
                rel_path = Path(rel)
                if rel_path.is_absolute() or ".." in rel_path.parts:
                    raise DriverError(f"File path must be relative and inside the project: {rel!r}")
                dest = stage_path / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
            rsync = self._run_local([
                "rsync", "-az",
                "-e", f"ssh -i {key} -o BatchMode=yes -o StrictHostKeyChecking=accept-new",
                f"{stage}/", f"{target}:{rdir}/",
            ], timeout_s=300)
            if rsync.exit_code != 0:
                raise DriverError(f"rsync failed: {rsync.stderr.strip()}")

    # ---------- execution ----------

    def _in_dir(self, sb: Sandbox, cmd: str) -> RunResult:
        rdir = sb.meta.get("remote_dir") or self._remote_dir(sb)
        return self._ssh(f"cd {shlex.quote(rdir)} && {cmd}")

    def build(self, sb: Sandbox, target: str | None) -> RunResult:
        if sb.lang in XCODE_LANGS:
            cmd = "xcodebuild build"
            if target:
                cmd += f" -scheme {shlex.quote(target)}"
            return self._in_dir(sb, cmd)
        # Swift Package Manager
        return self._in_dir(sb, "swift build")

    def test(self, sb: Sandbox, filter: str | None) -> RunResult:
        dest = self.config["mac"]["test_destination"]
        if sb.lang in XCODE_LANGS:
            if not filter:
                # xcodebuild test requires a scheme; make the requirement explicit
                # instead of failing with xcodebuild's own opaque error.
                return RunResult(
                    exit_code=2, stdout="",
                    stderr="xcodebuild test needs a scheme. Call run_tests with "
                           "filter=<SchemeName> (optionally SchemeName/TestClass/testMethod "
                           "via -only-testing is a future extension).",
                    log_path="", duration_ms=0,
                )
            cmd = f"xcodebuild test -scheme {shlex.quote(filter)} -destination {shlex.quote(dest)}"
            return self._in_dir(sb, cmd)
        cmd = "swift test"
        if filter:
            cmd += f" --filter {shlex.quote(filter)}"
        return self._in_dir(sb, cmd)

    def exec(self, sb: Sandbox, cmd: str) -> RunResult:
        return self._in_dir(sb, cmd)
