"""Tool-contract tests against the real server module (deps stubbed if absent)."""
import importlib

from ultra_sandbox.models import RunResult, Sandbox


def _fresh_server(monkeypatch, isolated_config):
    import ultra_sandbox.server as srv
    importlib.reload(srv)
    return srv


def test_contract_and_give_up(isolated_config, monkeypatch):
    srv = _fresh_server(monkeypatch, isolated_config)
    expected = {"create_sandbox", "write_files", "run_build", "run_tests",
                "exec_command", "get_logs", "search_docs", "destroy_sandbox",
                "list_sandboxes"}
    if hasattr(srv.mcp, "tools"):  # stubbed FastMCP exposes the registry
        assert expected <= set(srv.mcp.tools)

    sb = Sandbox(project_id="demo", lang="go", driver="docker")
    srv.state.add(sb)
    for i in range(srv.MAX_ATTEMPTS + 1):
        r = RunResult(exit_code=1, stdout="", stderr=f"err {i}", log_path="", duration_ms=1)
        srv.state.record_run(sb, "build", r)
    status = srv._loop_status(sb)
    assert "give_up" in status
    assert status["repair_attempts"] > status["max_attempts"] - 1


def test_shutdown_all_destroys(isolated_config, monkeypatch):
    srv = _fresh_server(monkeypatch, isolated_config)
    destroyed = []

    class FakeDriver:
        def destroy(self, sb):
            destroyed.append(sb.id)

    monkeypatch.setattr(srv.router, "by_name", lambda name: FakeDriver())
    sb = Sandbox(project_id="demo", lang="go", driver="docker")
    srv.state.add(sb)
    srv.shutdown_all()
    assert destroyed == [sb.id]
    assert srv.state.all()[0].status == "destroyed"
