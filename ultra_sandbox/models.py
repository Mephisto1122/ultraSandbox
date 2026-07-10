"""Data models shared across the server, drivers, state store, and dashboard."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any

# Sandbox lifecycle states shown on the dashboard.
STATUS_IDLE = "idle"
STATUS_BUILDING = "building"
STATUS_TESTING = "testing"
STATUS_PASSING = "passing"
STATUS_FAILING = "failing"
STATUS_DESTROYED = "destroyed"

from .languages import DOCKER_LANGS, MAC_LANGS  # single source of truth


def driver_for_lang(lang: str) -> str:
    lang = lang.lower()
    if lang in MAC_LANGS:
        return "mac"
    if lang in DOCKER_LANGS:
        return "docker"
    raise ValueError(
        f"Unknown language {lang!r}. Docker languages: {sorted(DOCKER_LANGS)}; "
        f"Mac languages: {sorted(MAC_LANGS)}."
    )


@dataclass
class RunResult:
    """Outcome of a single build / test / exec invocation."""

    exit_code: int
    stdout: str
    stderr: str
    log_path: str
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Attempt:
    """One entry in the repair-loop trace."""

    kind: str          # "build" | "test" | "exec"
    exit_code: int
    duration_ms: int
    ts: float
    summary: str       # first interesting line of output, for the dashboard

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Sandbox:
    project_id: str
    lang: str
    driver: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = STATUS_IDLE
    created_at: float = field(default_factory=time.time)
    attempts: list[Attempt] = field(default_factory=list)
    last_log_line: str = ""
    # Driver-specific bookkeeping (container name, remote dir, ...).
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def repair_attempts(self) -> int:
        """Failed build/test rounds so far — the number the loop cap counts."""
        return sum(1 for a in self.attempts if a.kind in ("build", "test") and a.exit_code != 0)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["repair_attempts"] = self.repair_attempts
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Sandbox":
        attempts = [Attempt(**a) for a in d.pop("attempts", [])]
        d.pop("repair_attempts", None)
        sb = Sandbox(**d)
        sb.attempts = attempts
        return sb
