"""Sandbox registry: in-memory, thread-safe, persisted to state.json.

The MCP server (stdio thread) writes; the dashboard HTTP server (its own
thread) reads — hence the lock. Persistence survives server restarts so a
long-running container from yesterday still shows up in list_sandboxes.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .config import Config
from .models import Attempt, RunResult, Sandbox


class State:
    def __init__(self, config: Config):
        self.config = config
        self._lock = threading.RLock()
        self._sandboxes: dict[str, Sandbox] = {}
        self._path = config.data_dir / "state.json"
        self._load()

    # ---------- persistence ----------

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            data = json.loads(self._path.read_text())
            for d in data.get("sandboxes", []):
                sb = Sandbox.from_dict(d)
                self._sandboxes[sb.id] = sb
        except (json.JSONDecodeError, TypeError, KeyError):
            # Corrupt state file: start fresh rather than crash.
            self._sandboxes = {}
            return
        # Ephemeral mode: sandboxes never outlive a session. Anything still
        # marked active in the state file belongs to a previous session whose
        # containers get reaped at startup — mark them destroyed here so the
        # registry and dashboard agree with reality.
        if self.config._raw.get("security", {}).get("ephemeral", True):
            for sb in self._sandboxes.values():
                if sb.status != "destroyed":
                    sb.status = "destroyed"
                    sb.last_log_line = "(previous session — reaped at startup)"

    def _save_locked(self) -> None:
        data = {"sandboxes": [sb.to_dict() for sb in self._sandboxes.values()]}
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self._path)

    # ---------- registry ----------

    def add(self, sb: Sandbox) -> None:
        with self._lock:
            self._sandboxes[sb.id] = sb
            self._save_locked()

    def get(self, sandbox_id: str) -> Sandbox:
        with self._lock:
            sb = self._sandboxes.get(sandbox_id)
        if sb is None:
            raise KeyError(f"No sandbox {sandbox_id!r}. Use list_sandboxes() to see active ones.")
        if sb.status == "destroyed":
            raise KeyError(f"Sandbox {sandbox_id!r} was destroyed. Create a new one.")
        return sb

    def all(self, include_destroyed: bool = True) -> list[Sandbox]:
        with self._lock:
            items = list(self._sandboxes.values())
        if not include_destroyed:
            items = [s for s in items if s.status != "destroyed"]
        return sorted(items, key=lambda s: s.created_at, reverse=True)

    def update(self, sb: Sandbox, *, status: str | None = None) -> None:
        with self._lock:
            if status is not None:
                sb.status = status
            self._sandboxes[sb.id] = sb
            self._save_locked()

    # ---------- repair-loop trace + logs ----------

    def record_run(self, sb: Sandbox, kind: str, result: RunResult) -> None:
        """Append to the sandbox's trace and update status + last log line."""
        text = (result.stdout + "\n" + result.stderr).strip()
        lines = [ln for ln in text.splitlines() if ln.strip()]
        # For failures, the last lines are usually the interesting ones.
        summary = (lines[-1] if result.exit_code != 0 else (lines[-1] if lines else "ok"))[:200]
        with self._lock:
            sb.attempts.append(Attempt(
                kind=kind, exit_code=result.exit_code,
                duration_ms=result.duration_ms, ts=time.time(), summary=summary,
            ))
            sb.last_log_line = summary
            if kind == "build":
                sb.status = "failing" if result.exit_code != 0 else "idle"
            elif kind == "test":
                sb.status = "failing" if result.exit_code != 0 else "passing"
            self._save_locked()

    def log_file(self, sb: Sandbox, kind: str) -> Path:
        return self.config.log_dir(sb.id) / f"{kind}.log"

    def append_log(self, sb: Sandbox, kind: str, result: RunResult, header: str) -> str:
        path = self.log_file(sb, kind)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        block = (
            f"\n===== {stamp} | {header} | exit={result.exit_code} "
            f"| {result.duration_ms} ms =====\n"
            f"{result.stdout}"
            + (f"\n--- stderr ---\n{result.stderr}" if result.stderr.strip() else "")
            + "\n"
        )
        with open(path, "a", encoding="utf-8", errors="replace") as f:
            f.write(block)
        return str(path)

    def read_logs(self, sb: Sandbox, kind: str | None = None, since_line: int = 0) -> dict:
        kinds = [kind] if kind else ["build", "test", "exec"]
        out: dict[str, dict] = {}
        for k in kinds:
            path = self.log_file(sb, k)
            if not path.is_file():
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            out[k] = {
                "total_lines": len(lines),
                "lines": lines[since_line:],
            }
        return out
