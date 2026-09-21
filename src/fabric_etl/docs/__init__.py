"""Doc emitters over the registry: markdown, dbml, jsonschema, lineage, drivers.

Submodules load lazily so importing fabric_etl.docs stays pydantic-only.
"""

import importlib
from typing import Any

_SUBMODULES = ("dbml", "drivers", "jsonschema", "lineage", "markdown")

__all__ = list(_SUBMODULES)


def __getattr__(name: str) -> Any:
    if name in _SUBMODULES:
        return importlib.import_module(f"fabric_etl.docs.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
