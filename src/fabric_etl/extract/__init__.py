"""Readers driven by source entities. Re-exports are lazy so importing this
package never pulls optional heavy deps (lxml, pyodbc)."""

from typing import Any

_HOME = {
    "sql": "sql",
    "select_sql": "sql",
    "xml": "xml",
    "csv": "csv",
    "Cdc": "cdc",
    "CdcOperation": "cdc",
    "capture_instance": "cdc",
    "max_lsn": "cdc",
    "changes": "cdc",
    "get_watermark": "cdc",
    "set_watermark": "cdc",
    "window": "cdc",
}


def __getattr__(name: str) -> Any:
    if name not in _HOME:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(f"fabric_etl.extract.{_HOME[name]}"), name)
    globals()[name] = value  # shadow the submodule attr the import just set
    return value
