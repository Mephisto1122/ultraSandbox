"""Cost tracking.

Docker is effectively free (your machine). The EC2 Mac dedicated host is the
real cost, and — per the build plan's open question — we track it locally
against the published hourly rate rather than the Cost Explorer API, because
Cost Explorer data lags ~a day and this dashboard wants live numbers.

The unit that matters is the 24-hour minimum billing block: once a dedicated
host is allocated, AWS bills at least 24 hours of it. So the dashboard shows
"Xh remaining in current block" instead of a misleading live dollar ticker.

The host allocation clock is started/stopped explicitly (mark_allocated /
mark_released), not tied to sandbox lifecycle — a 10-minute Swift build should
not silently start a 24-hour bill without you deciding to.
"""

from __future__ import annotations

import json
import math
import time

from .config import Config

BLOCK_HOURS = 24


class MacHostClock:
    def __init__(self, config: Config):
        self.config = config
        self._path = config.data_dir / "mac_host.json"

    def _read(self) -> dict:
        if self._path.is_file():
            try:
                return json.loads(self._path.read_text())
            except json.JSONDecodeError:
                pass
        return {}

    def mark_allocated(self, when: float | None = None) -> None:
        data = self._read()
        if not data.get("allocated_at"):
            data["allocated_at"] = when or time.time()
            data.pop("released_at", None)
            self._path.write_text(json.dumps(data))

    def mark_released(self) -> None:
        data = self._read()
        if data.get("allocated_at"):
            data["released_at"] = time.time()
            self._path.write_text(json.dumps(data))

    def summary(self) -> dict:
        rate = float(self.config["mac"]["hourly_rate"])
        data = self._read()
        allocated_at = data.get("allocated_at")
        if not allocated_at:
            return {
                "allocated": False,
                "hourly_rate": rate,
                "message": "No Mac host allocation being tracked.",
            }
        end = data.get("released_at") or time.time()
        hours = max((end - allocated_at) / 3600.0, 0.0)
        blocks = max(1, math.ceil(hours / BLOCK_HOURS))
        billed_hours = blocks * BLOCK_HOURS
        remaining_h = billed_hours - hours if not data.get("released_at") else 0.0
        return {
            "allocated": not data.get("released_at"),
            "allocated_at": allocated_at,
            "elapsed_hours": round(hours, 2),
            "billing_blocks": blocks,
            "billed_hours": billed_hours,
            "estimated_cost_usd": round(billed_hours * rate, 2),
            "hourly_rate": rate,
            "remaining_in_block_hours": round(remaining_h, 2),
        }
