import sys

import pytest

from fabric_etl.settings import FabricSettings


class DemoSettings(FabricSettings):
    server: str = "localhost"
    database: str | None = None


def test_env_source_with_prefix(monkeypatch):
    monkeypatch.setenv("FABRIC_ETL_SERVER", "sql.example.com")
    monkeypatch.setenv("FABRIC_ETL_DATABASE", "dwh")
    s = DemoSettings()
    assert s.server == "sql.example.com"
    assert s.database == "dwh"


def test_env_wins_over_field_default(monkeypatch):
    monkeypatch.setenv("FABRIC_ETL_SERVER", "from-env")
    assert DemoSettings().server == "from-env"


def test_init_kwarg_wins_over_env(monkeypatch):
    monkeypatch.setenv("FABRIC_ETL_SERVER", "from-env")
    assert DemoSettings(server="from-init").server == "from-init"


def test_extra_env_ignored(monkeypatch):
    monkeypatch.setenv("FABRIC_ETL_UNKNOWN", "x")
    assert DemoSettings().server == "localhost"


def test_keyvault_url_without_azure_raises(monkeypatch):
    with pytest.raises(ImportError, match=r"fabric-etl\[azure\]"):
        DemoSettings(keyvault_url="https://kv.vault.azure.net")


def test_keyvault_url_env_without_azure_raises(monkeypatch):
    monkeypatch.setenv("FABRIC_ETL_KEYVAULT_URL", "https://kv.vault.azure.net")
    with pytest.raises(ImportError, match=r"fabric-etl\[azure\]"):
        DemoSettings()


def test_no_keyvault_url_no_azure_import(monkeypatch):
    monkeypatch.delenv("FABRIC_ETL_KEYVAULT_URL", raising=False)
    s = DemoSettings()
    assert s.keyvault_url is None
    assert "azure.identity" not in sys.modules
