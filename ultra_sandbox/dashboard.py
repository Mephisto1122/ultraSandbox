"""Read-only status dashboard.

A small stdlib HTTP server in a daemon thread beside the MCP server: no extra
dependencies, no writes — it only reads the same State the MCP tools write.

Endpoints:
  GET /                → static/index.html
  GET /api/sandboxes   → sandbox list + mac host cost summary
  GET /api/trace?id=   → repair-loop attempts for one sandbox
  GET /api/logs?id=&kind=&since=  → captured log lines
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import Config
from .cost import MacHostClock
from .state import State

STATIC_DIR = Path(__file__).resolve().parent / "static"


def make_handler(state: State, mac_clock: MacHostClock, max_attempts: int):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep stdio clean — stdio is the MCP transport
            pass

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj).encode(), "application/json")

        def do_GET(self):  # noqa: N802
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path in ("/", "/index.html"):
                    html = (STATIC_DIR / "index.html").read_bytes()
                    self._send(200, html, "text/html; charset=utf-8")
                elif url.path == "/api/sandboxes":
                    self._json(self._sandboxes())
                elif url.path == "/api/trace":
                    sb = state.get(q["id"])
                    self._json({"id": sb.id, "attempts": [a.to_dict() for a in sb.attempts],
                                "max_attempts": max_attempts})
                elif url.path == "/api/logs":
                    sb = state.get(q["id"])
                    self._json({"id": sb.id, "logs": state.read_logs(
                        sb, kind=q.get("kind"), since_line=int(q.get("since", 0)))})
                else:
                    self._json({"error": "not found"}, 404)
            except KeyError as e:
                self._json({"error": str(e)}, 404)
            except Exception as e:  # dashboard must never take down the MCP server
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

        def _sandboxes(self) -> dict:
            mac = mac_clock.summary()
            items = []
            for sb in state.all():
                items.append({
                    "id": sb.id,
                    "project_id": sb.project_id,
                    "lang": sb.lang,
                    "driver": sb.driver,
                    "status": sb.status,
                    "created_at": sb.created_at,
                    "repair_attempts": sb.repair_attempts,
                    "attempts": [a.to_dict() for a in sb.attempts],
                    "last_log_line": sb.last_log_line,
                })
            return {"sandboxes": items, "mac_host": mac, "max_attempts": max_attempts}

    return Handler


def start_dashboard(config: Config, state: State, mac_clock: MacHostClock) -> threading.Thread:
    port = int(config["server"]["dashboard_port"])
    handler = make_handler(state, mac_clock, int(config["server"]["max_attempts"]))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, name="dashboard", daemon=True)
    thread.start()
    return thread
