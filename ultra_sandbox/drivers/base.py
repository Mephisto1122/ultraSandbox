"""The driver contract. Claude never sees this — it sees the MCP tools —
but both backends (Docker, SSH-Mac) implement exactly this interface so the
router can treat them interchangeably.
"""

from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod

from ..config import Config
from ..models import RunResult, Sandbox


class DriverError(RuntimeError):
    """Raised for environment problems (docker missing, ssh unreachable, ...).

    Distinct from a failing build: a failing build is a *successful* tool call
    with exit_code != 0 that Claude is expected to repair.
    """


class Driver(ABC):
    name: str = "base"

    def __init__(self, config: Config):
        self.config = config

    # ---- lifecycle ----
    @abstractmethod
    def create(self, sb: Sandbox, deps: list[str] | None, allow_network: bool = False) -> None: ...

    @abstractmethod
    def destroy(self, sb: Sandbox) -> None: ...

    # ---- file sync ----
    @abstractmethod
    def write_files(self, sb: Sandbox, files: dict[str, str]) -> None: ...

    # ---- execution ----
    @abstractmethod
    def build(self, sb: Sandbox, target: str | None) -> RunResult: ...

    @abstractmethod
    def test(self, sb: Sandbox, filter: str | None) -> RunResult: ...

    @abstractmethod
    def exec(self, sb: Sandbox, cmd: str) -> RunResult: ...

    # ---- shared helper ----
    def _run_local(self, argv: list[str], timeout_s: int | None = None,
                   input_text: str | None = None) -> RunResult:
        """Run a local process (docker/ssh/rsync) and capture everything."""
        timeout = timeout_s or self.config["server"]["command_timeout_s"]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True,
                timeout=timeout, input=input_text,
            )
            code, out, err = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as e:
            code = 124
            out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            err = f"Timed out after {timeout}s. Command: {' '.join(argv[:6])}..."
        except FileNotFoundError as e:
            raise DriverError(f"Required local binary not found: {e.filename}") from e
        duration = int((time.monotonic() - start) * 1000)
        return RunResult(exit_code=code, stdout=out, stderr=err,
                         log_path="", duration_ms=duration)
