"""Test fixtures. Stubs `mcp` and `httpx` only if they aren't installed, so the
suite runs both in bare environments and in CI with real dependencies."""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _stub_missing_deps() -> None:
    try:
        import httpx  # noqa: F401
    except ImportError:
        httpx = types.ModuleType("httpx")

        class HTTPError(Exception):
            pass

        httpx.HTTPError = HTTPError
        httpx.get = lambda *a, **k: (_ for _ in ()).throw(HTTPError("offline"))
        sys.modules["httpx"] = httpx

    try:
        from mcp.server.fastmcp import FastMCP  # noqa: F401
    except ImportError:
        mcp_pkg = types.ModuleType("mcp")
        server_mod = types.ModuleType("mcp.server")
        fastmcp_mod = types.ModuleType("mcp.server.fastmcp")

        class FastMCP:
            def __init__(self, name):
                self.name, self.tools = name, {}

            def tool(self, *a, **k):
                def deco(fn):
                    self.tools[fn.__name__] = fn
                    return fn
                return deco

            def run(self):
                pass

        fastmcp_mod.FastMCP = FastMCP
        sys.modules["mcp"] = mcp_pkg
        sys.modules["mcp.server"] = server_mod
        sys.modules["mcp.server.fastmcp"] = fastmcp_mod


_stub_missing_deps()


@pytest.fixture()
def isolated_config(tmp_path, monkeypatch):
    """Point the config loader at a throwaway data dir."""
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[server]\ndata_dir = "{tmp_path / "data"}"\n[docs]\nprovider = "none"\n')
    monkeypatch.setenv("ULTRA_SANDBOX_CONFIG", str(cfg))
    monkeypatch.delenv("ULTRA_SANDBOX_DASHBOARD_PORT", raising=False)
    from ultra_sandbox.config import load_config
    return load_config()
