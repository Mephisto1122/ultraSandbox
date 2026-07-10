"""Configuration: TOML file merged over defaults.

Search order: $ULTRA_SANDBOX_CONFIG, ./config.toml, ~/.ultra-sandbox/config.toml.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "server": {
        "dashboard_port": 8787,
        "max_attempts": 8,
        "command_timeout_s": 900,
        "data_dir": "~/.ultra-sandbox",
    },
    "docker": {
        "memory": "4g",
        "cpus": "2",
        "image_prefix": "ultra-sandbox",
    },
    "security": {
        # Destroy every sandbox when the server exits, and reap stale
        # containers/volumes from previous sessions at startup.
        "ephemeral": True,
        # Default container network: "none" = no network at all.
        # create_sandbox(allow_network=True) opts a single sandbox into "bridge".
        "network": "none",
        # Default network for sandboxes created WITHOUT an explicit allow_network:
        #   "none"   — isolated; builds that fetch deps must pass allow_network=true
        #   "bridge" — full internet by default (git clone, pip/npm/cargo/go get all
        #              work out of the box). Convenient; less isolated.
        "default_network": "none",
        # Immutable root filesystem; only /work (volume) and /tmp (tmpfs) are writable.
        "read_only_rootfs": True,
        "pids_limit": 512,
        "tmpfs_size": "512m",
    },
    "mac": {
        "host": "",
        "user": "ec2-user",
        "key": "~/.ssh/mac.pem",
        "remote_root": "/Users/ec2-user/ultra-sandbox",
        "hourly_rate": 0.65,
        "test_destination": "platform=macOS",
    },
    "docs": {
        "provider": "brave",
        "allowlist": [
            "pkg.go.dev", "go.dev",
            "developer.apple.com",
            "developer.mozilla.org", "nodejs.org",
            "docs.python.org", "pypi.org",
            "doc.rust-lang.org", "docs.rs",
            "cmake.org", "en.cppreference.com",
            "learn.microsoft.com",
            "docs.oracle.com", "kotlinlang.org",
        ],
    },
}


import copy


def _deep_merge(base: dict, override: dict) -> dict:
    # Deep-copy the base so the returned config never shares nested dict
    # references with module-level DEFAULTS — otherwise mutating a loaded config
    # would silently alter the defaults for every later load.
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


class Config:
    def __init__(self, raw: dict[str, Any]):
        self._raw = raw

    def __getitem__(self, section: str) -> dict[str, Any]:
        return self._raw[section]

    @property
    def data_dir(self) -> Path:
        p = Path(self._raw["server"]["data_dir"]).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        (p / "logs").mkdir(exist_ok=True)
        return p

    def log_dir(self, sandbox_id: str) -> Path:
        d = self.data_dir / "logs" / sandbox_id
        d.mkdir(parents=True, exist_ok=True)
        return d


def load_config() -> Config:
    candidates = []
    if env := os.environ.get("ULTRA_SANDBOX_CONFIG"):
        candidates.append(Path(env))
    candidates.append(Path.cwd() / "config.toml")
    candidates.append(Path("~/.ultra-sandbox/config.toml").expanduser())

    raw = DEFAULTS
    for path in candidates:
        if path.is_file():
            with open(path, "rb") as f:
                raw = _deep_merge(DEFAULTS, tomllib.load(f))
            break

    # Env overrides (used by the Desktop Extension / MCPB user_config fields,
    # which pass values in through the environment rather than a config file).
    if port := os.environ.get("ULTRA_SANDBOX_DASHBOARD_PORT"):
        try:
            raw = _deep_merge(raw, {"server": {"dashboard_port": int(port)}})
        except ValueError:
            pass
    return Config(raw)
