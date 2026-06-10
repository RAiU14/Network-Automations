from __future__ import annotations

from app.core.runtime_config import read_runtime_config, write_runtime_database_url


def test_runtime_database_config_uses_env_file_not_json(tmp_path, monkeypatch) -> None:
    runtime_file = tmp_path / ".eox_runtime.env"
    export_file = tmp_path / ".env.local"
    monkeypatch.setenv("EOX_RUNTIME_CONFIG_FILE", str(runtime_file))
    monkeypatch.setenv("EOX_ENV_EXPORT_FILE", str(export_file))

    written = write_runtime_database_url("sqlite:///tmp/eox_dev.db")
    read_back = read_runtime_config()

    assert written.database_url == "sqlite:///tmp/eox_dev.db"
    assert read_back.database_url == "sqlite:///tmp/eox_dev.db"
    assert runtime_file.exists()
    assert "EOX_DATABASE_URL=sqlite:///tmp/eox_dev.db" in runtime_file.read_text()
    assert not runtime_file.read_text().lstrip().startswith("{")
    assert export_file.exists()
