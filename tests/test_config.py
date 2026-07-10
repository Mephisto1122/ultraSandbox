def test_defaults_and_env_port(isolated_config, monkeypatch):
    assert isolated_config["security"]["network"] == "none"
    assert isolated_config["security"]["ephemeral"] is True

    monkeypatch.setenv("ULTRA_SANDBOX_DASHBOARD_PORT", "9999")
    from ultra_sandbox.config import load_config
    assert load_config()["server"]["dashboard_port"] == 9999

    monkeypatch.setenv("ULTRA_SANDBOX_DASHBOARD_PORT", "nope")
    assert load_config()["server"]["dashboard_port"] == 8787
