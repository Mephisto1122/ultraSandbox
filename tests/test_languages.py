"""Guards against language/Dockerfile/command drift — the class of bug where a
language is accepted by create_sandbox but has no build command or image."""
from pathlib import Path

import pytest

from ultra_sandbox.drivers.base import DriverError
from ultra_sandbox.drivers.docker_driver import DockerDriver, NETWORK_HUNGRY
from ultra_sandbox.languages import DOCKER_LANGS, LANGUAGES, MAC_LANGS
from ultra_sandbox.models import RunResult, Sandbox, driver_for_lang

IMAGES = Path(__file__).resolve().parent.parent / "ultra_sandbox" / "images"


def test_every_docker_language_is_complete():
    for name in DOCKER_LANGS:
        spec = LANGUAGES[name]
        assert (IMAGES / name / "Dockerfile").is_file(), f"{name}: no Dockerfile"
        assert spec.build.strip(), f"{name}: empty build command"
        assert spec.test.strip(), f"{name}: empty test command"


def test_no_orphan_dockerfiles():
    dirs = {p.name for p in IMAGES.iterdir() if p.is_dir()}
    assert dirs == set(DOCKER_LANGS), f"drift: dirs={dirs} langs={set(DOCKER_LANGS)}"


def test_routing_covers_registry():
    for name in DOCKER_LANGS:
        assert driver_for_lang(name) == "docker"
    for name in MAC_LANGS:
        assert driver_for_lang(name) == "mac"


def test_language_count():
    # 22 docker + 3 mac; update deliberately when adding languages.
    assert len(DOCKER_LANGS) == 22
    assert len(MAC_LANGS) == 3


class CapturingDriver(DockerDriver):
    def __init__(self, config):
        super().__init__(config)
        self.execs = []

    def _run_local(self, argv, timeout_s=None, input_text=None):
        if argv[:2] == ["docker", "exec"] and "sh" in argv:
            self.execs.append(argv[-1])  # the shell command string
        if argv[:2] == ["docker", "volume"] and argv[2] == "create":
            return RunResult(0, argv[3], "", "", 1)
        return RunResult(0, "", "", "", 1)

    def _ensure_image(self, lang):
        pass


@pytest.mark.parametrize("lang", sorted(DOCKER_LANGS))
def test_build_dispatches_correct_command(isolated_config, lang):
    d = CapturingDriver(isolated_config)
    sb = Sandbox(project_id="p", lang=lang, driver="docker")
    d.create(sb, None, allow_network=LANGUAGES[lang].network_build)
    d.build(sb, None)
    d.test(sb, None)
    # the registry's build+test strings were the ones dispatched
    assert LANGUAGES[lang].build in d.execs
    assert LANGUAGES[lang].test in d.execs


def test_network_hungry_langs_gated(isolated_config):
    d = CapturingDriver(isolated_config)
    for lang in NETWORK_HUNGRY:
        with pytest.raises(DriverError, match="allow_network"):
            d.create(Sandbox(project_id="p", lang=lang, driver="docker"), None)
