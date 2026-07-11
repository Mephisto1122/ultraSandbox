"""The security flags are the product: verify every hardened container option
is present on `docker run`, without needing Docker itself (calls are captured)."""
import pytest

from ultra_sandbox.drivers.base import DriverError
from ultra_sandbox.drivers.docker_driver import DockerDriver
from ultra_sandbox.models import RunResult, Sandbox


class CapturingDriver(DockerDriver):
    def __init__(self, config):
        super().__init__(config)
        self.calls = []

    def _run_local(self, argv, timeout_s=None, input_text=None):
        self.calls.append(argv)
        return RunResult(exit_code=0, stdout="", stderr="", log_path="", duration_ms=1)

    def _ensure_image(self, lang):
        pass


def _run_argv(driver):
    return next(c for c in driver.calls if c[:2] == ["docker", "run"])


def test_hardened_run_flags(isolated_config):
    d = CapturingDriver(isolated_config)
    sb = Sandbox(project_id="p", lang="go", driver="docker")
    d.create(sb, None)
    argv = _run_argv(d)

    for flag in ("--network", "--cap-drop", "--pids-limit", "--read-only",
                 "--memory", "--cpus", "--tmpfs"):
        assert flag in argv, f"missing {flag}"
    assert argv[argv.index("--network") + 1] == "none"
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert ["--security-opt", "no-new-privileges"] == \
        argv[argv.index("--security-opt"):argv.index("--security-opt") + 2]
    # per-sandbox volume, no host bind mounts
    vol = argv[argv.index("-v") + 1]
    assert vol.startswith("us_") and ":/work" in vol and "/" not in vol.split(":")[0]
    assert sb.meta["network"] == "none"


def test_allow_network_switches_to_bridge(isolated_config):
    d = CapturingDriver(isolated_config)
    sb = Sandbox(project_id="p", lang="go", driver="docker")
    d.create(sb, None, allow_network=True)
    argv = _run_argv(d)
    assert argv[argv.index("--network") + 1] == "bridge"


def test_network_hungry_lang_refused_offline(isolated_config):
    d = CapturingDriver(isolated_config)
    sb = Sandbox(project_id="p", lang="node", driver="docker")
    with pytest.raises(DriverError, match="allow_network"):
        d.create(sb, None)


def test_deps_refused_offline(isolated_config):
    d = CapturingDriver(isolated_config)
    sb = Sandbox(project_id="p", lang="go", driver="docker")
    with pytest.raises(DriverError, match="allow_network"):
        d.create(sb, ["github.com/stretchr/testify"])


def test_path_traversal_rejected(isolated_config):
    d = CapturingDriver(isolated_config)
    sb = Sandbox(project_id="p", lang="go", driver="docker")
    sb.meta["container"] = "us_x"
    for bad in ("../../etc/passwd", "/abs/path.go"):
        with pytest.raises(DriverError):
            d.write_files(sb, {bad: "x"})


def test_destroy_removes_container_and_volume(isolated_config):
    d = CapturingDriver(isolated_config)
    sb = Sandbox(project_id="p", lang="go", driver="docker")
    d.create(sb, None)
    d.destroy(sb)
    flat = [" ".join(c) for c in d.calls]
    assert any(s.startswith("docker rm -f us_") for s in flat)
    assert any(s.startswith("docker volume rm -f us_") for s in flat)


def test_default_network_bridge_allows_downloads(isolated_config):
    """With default_network=bridge, a sandbox gets network without allow_network,
    so git clone / dep installs work out of the box."""
    isolated_config._raw["security"]["default_network"] = "bridge"
    d = CapturingDriver(isolated_config)
    sb = Sandbox(project_id="p", lang="node", driver="docker")  # network-hungry
    d.create(sb, None)  # no allow_network needed now
    assert sb.meta["network"] == "bridge"


def test_git_installed_in_every_image():
    """git must be present in every image so clones + git-based deps work."""
    from pathlib import Path
    images = Path(__file__).resolve().parent.parent / "ultra_sandbox" / "images"
    for df in images.glob("*/Dockerfile"):
        assert "git" in df.read_text(), f"{df.parent.name}: no git in image"


def test_uses_non_login_shell_and_pins_path(isolated_config):
    """Regression: `sh -lc` re-sources /etc/profile and resets PATH, which made
    go/cargo 'not found' even though the binaries existed. Must use `sh -c` and
    pass an explicit PATH covering the toolchain dirs."""
    from ultra_sandbox.drivers.docker_driver import SANDBOX_PATH

    d = CapturingDriver(isolated_config)
    sb = Sandbox(project_id="p", lang="go", driver="docker")
    d.create(sb, None)
    argv = _run_argv(d)

    # PATH is injected into the container env...
    env = [argv[i + 1] for i, a in enumerate(argv) if a == "-e"]
    path_var = next(e for e in env if e.startswith("PATH="))
    for needed in ("/usr/local/go/bin", "/usr/local/cargo/bin", "/work/.home/.local/bin"):
        assert needed in path_var, f"PATH missing {needed}"

    # ...and commands run in a NON-login shell.
    d.build(sb, None)
    exec_calls = [c for c in d.calls if c[:2] == ["docker", "exec"]]
    shells = [c for c in exec_calls if "sh" in c]
    assert shells, "no shell exec captured"
    for c in shells:
        assert "-lc" not in c, "login shell (-lc) resets PATH — must use -c"
