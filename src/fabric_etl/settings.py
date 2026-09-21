"""Typed runtime configuration via pydantic-settings; requires the [settings] extra."""

import os

try:
    from pydantic_settings import (
        BaseSettings,
        PydanticBaseSettingsSource,
        SettingsConfigDict,
    )
except ImportError as exc:
    raise ImportError(
        "fabric_etl.settings requires pydantic-settings; install fabric-etl[settings]"
    ) from exc

__all__ = ["FabricSettings"]


class FabricSettings(BaseSettings):
    """Base settings class for fabric-etl configuration.

    Subclass and declare fields; values resolve from init kwargs, then
    ``FABRIC_ETL_``-prefixed environment variables, then dotenv, then file
    secrets. When ``keyvault_url`` is set (init kwarg or
    ``FABRIC_ETL_KEYVAULT_URL``), an Azure Key Vault source is appended last,
    so any env value wins over Key Vault. The Key Vault source needs the
    [azure] extra and authenticates with ``DefaultAzureCredential``.

    Caveat: inside Fabric notebooks verify that ``DefaultAzureCredential``
    resolves the executing identity; ``notebookutils.credentials`` is the
    fallback path if it does not (not implemented here).
    """

    model_config = SettingsConfigDict(env_prefix="FABRIC_ETL_", extra="ignore")

    keyvault_url: str | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        sources = (init_settings, env_settings, dotenv_settings, file_secret_settings)
        prefix = settings_cls.model_config.get("env_prefix", "")
        url = getattr(init_settings, "init_kwargs", {}).get("keyvault_url") or os.environ.get(
            f"{prefix}KEYVAULT_URL"
        )
        if not url:
            return sources
        try:
            from azure.identity import DefaultAzureCredential
            from pydantic_settings import AzureKeyVaultSettingsSource

            keyvault = AzureKeyVaultSettingsSource(
                settings_cls, url=url, credential=DefaultAzureCredential()
            )
        except ImportError as exc:
            raise ImportError(
                "keyvault_url is set but the Azure Key Vault dependencies are missing; "
                "install fabric-etl[azure]"
            ) from exc
        return (*sources, keyvault)
