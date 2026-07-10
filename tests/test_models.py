import pytest

from ultra_sandbox.models import Sandbox, driver_for_lang


def test_router_langs():
    assert driver_for_lang("go") == "docker"
    assert driver_for_lang("SWIFT") == "mac"
    with pytest.raises(ValueError):
        driver_for_lang("cobol")


def test_sandbox_roundtrip():
    sb = Sandbox(project_id="p", lang="go", driver="docker")
    sb2 = Sandbox.from_dict(sb.to_dict())
    assert sb2.id == sb.id and sb2.lang == "go"
