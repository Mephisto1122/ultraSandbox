"""Entry point: `python -m ultra_sandbox` or the `ultra-sandbox` script.

Session lifecycle (ephemeral security mode, on by default):
1. Reap stale sandboxes left by any previous/crashed session.
2. Start the read-only dashboard in a daemon thread.
3. Serve MCP over stdio until the client disconnects.
4. Destroy every sandbox created during the session (atexit + SIGTERM/SIGINT).

Nothing but the MCP protocol may print to stdout — stdio is the transport.
"""

from __future__ import annotations

import atexit
import signal
import sys


def main() -> None:
    from .dashboard import start_dashboard
    from .server import config, mac_clock, mcp, reap_previous_sessions, shutdown_all, state

    reap_previous_sessions()
    atexit.register(shutdown_all)

    def _terminate(signum, frame):  # noqa: ARG001
        sys.exit(0)  # triggers atexit -> shutdown_all

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _terminate)
        except (ValueError, OSError):
            pass  # not the main thread, or unsupported on this platform

    start_dashboard(config, state, mac_clock)
    print(
        f"ultra-sandbox: dashboard on http://localhost:{config['server']['dashboard_port']}"
        + (" | ephemeral mode: sandboxes are destroyed on exit"
           if config["security"]["ephemeral"] else ""),
        file=sys.stderr,
    )
    mcp.run()  # stdio transport; blocks until the client disconnects


if __name__ == "__main__":
    main()
