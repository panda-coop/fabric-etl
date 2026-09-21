"""Loaders: DDL, drift plan, writers, control entities. Lazy re-exports so
importing fabric_etl.load never pulls pyspark or a DB driver."""

import importlib

_EXPORTS = {
    "ddl": "fabric_etl.load.ddl",
    "PlanAction": "fabric_etl.load.plan",
    "plan": "fabric_etl.load.plan",
    "warehouse": "fabric_etl.load.writers",
    "lakehouse": "fabric_etl.load.writers",
    "to_spark_schema": "fabric_etl.load.spark",
    "RunLog": "fabric_etl.load.control",
    "Watermark": "fabric_etl.load.control",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    if name in _EXPORTS:
        return getattr(importlib.import_module(_EXPORTS[name]), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
