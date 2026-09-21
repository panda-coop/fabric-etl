"""Entity -> pyspark StructType. pyspark is imported lazily ([spark] extra)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fabric_etl.entities.columns import ColumnInfo
from fabric_etl.entities.drivers.base import UnsupportedType


def _spark_type(types, c: ColumnInfo):
    if c.py_type is Decimal:
        return types.DecimalType(c.col.precision or 18, c.col.scale or 0)
    simple = {
        int: types.LongType,
        float: types.DoubleType,
        bool: types.BooleanType,
        str: types.StringType,
        datetime: types.TimestampType,
        date: types.DateType,
        bytes: types.BinaryType,
        UUID: types.StringType,
    }
    if c.py_type in simple:
        return simple[c.py_type]()
    raise UnsupportedType(f"spark: unsupported column type {c.py_type.__name__} ({c.attr})")


def to_spark_schema(entity_cls: type):
    """StructType with physical column names; nullable from Optional."""
    try:
        from pyspark.sql import types
    except ImportError as e:
        raise ImportError(
            "pyspark is required for to_spark_schema — install fabric-etl[spark]"
        ) from e
    info = entity_cls.__entity__
    return types.StructType(
        [
            types.StructField(c.physical, _spark_type(types, c), nullable=c.optional)
            for c in info.columns
        ]
    )
