from ultra_sandbox.models import RunResult, Sandbox
from ultra_sandbox.state import State


def _fail(msg="boom"):
    return RunResult(exit_code=1, stdout="", stderr=msg, log_path="", duration_ms=5)


def test_trace_logs_and_persistence(isolated_config):
    st = State(isolated_config)
    sb = Sandbox(project_id="demo", lang="go", driver="docker")
    st.add(sb)

    for i in range(3):
        r = _fail(f"err {i}")
        r.log_path = st.append_log(sb, "build", r, header=f"run {i}")
        st.record_run(sb, "build", r)
    assert sb.repair_attempts == 3
    assert sb.status == "failing"

    ok = RunResult(exit_code=0, stdout="ok", stderr="", log_path="", duration_ms=5)
    st.record_run(sb, "test", ok)
    assert sb.status == "passing"

    logs = st.read_logs(sb, kind="build")
    total = logs["build"]["total_lines"]
    tail = st.read_logs(sb, kind="build", since_line=total - 1)
    assert len(tail["build"]["lines"]) == 1

    # Reload: ephemeral mode marks survivors destroyed (session-scoped).
    st2 = State(isolated_config)
    survivors = [s for s in st2.all() if s.id == sb.id]
    assert survivors and survivors[0].status == "destroyed"
    assert survivors[0].repair_attempts == 3  # trace survives for the dashboard
