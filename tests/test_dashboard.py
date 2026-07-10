import http.client
import json
import time

from ultra_sandbox.cost import MacHostClock
from ultra_sandbox.dashboard import start_dashboard
from ultra_sandbox.models import RunResult, Sandbox
from ultra_sandbox.state import State


def test_endpoints(isolated_config):
    isolated_config._raw["server"]["dashboard_port"] = 8871
    st = State(isolated_config)
    clk = MacHostClock(isolated_config)
    sb = Sandbox(project_id="widget", lang="rust", driver="docker")
    st.add(sb)
    r = RunResult(1, "compiling", "error[E0425]", "", 10)
    r.log_path = st.append_log(sb, "build", r, "run_build")
    st.record_run(sb, "build", r)

    start_dashboard(isolated_config, st, clk)
    time.sleep(0.3)

    def get(path):
        c = http.client.HTTPConnection("127.0.0.1", 8871, timeout=5)
        c.request("GET", path)
        resp = c.getresponse()
        return resp.status, resp.read()

    code, html = get("/")
    assert code == 200 and b"Repair loop" in html
    code, body = get("/api/sandboxes")
    assert json.loads(body)["sandboxes"][0]["status"] == "failing"
    code, body = get(f"/api/logs?id={sb.id}&kind=build")
    assert b"E0425" in body
    code, _ = get("/api/trace?id=missing")
    assert code == 404
