"""Tests for load.spark — fake pyspark injected into sys.modules."""

import sys
import types as pytypes
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import pytest
from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import Warehouse
from fabric_etl.entities.drivers.base import UnsupportedType
from fabric_etl.load.spark import to_spark_schema


class _Node:
    """Recording stand-in for a pyspark type: equality on constructor args."""

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs

    def __eq__(self, other):
        return type(self) is type(other) and (self.args, self.kwargs) == (other.args, other.kwargs)

    def __repr__(self):
        return f"{type(self).__name__}({self.args}, {self.kwargs})"


class LongType(_Node): ...


class DoubleType(_Node): ...


class DecimalType(_Node): ...


class BooleanType(_Node): ...


class StringType(_Node): ...


class TimestampType(_Node): ...


class DateType(_Node): ...


class BinaryType(_Node): ...


class StructField(_Node): ...


class StructType(_Node): ...


_FAKE_TYPES = (
    LongType,
    DoubleType,
    DecimalType,
    BooleanType,
    StringType,
    TimestampType,
    DateType,
    BinaryType,
    StructField,
    StructType,
)


@pytest.fixture
def fake_pyspark(monkeypatch):
    types_mod = pytypes.ModuleType("pyspark.sql.types")
    for cls in _FAKE_TYPES:
        setattr(types_mod, cls.__name__, cls)
    sql_mod = pytypes.ModuleType("pyspark.sql")
    sql_mod.types = types_mod
    pyspark_mod = pytypes.ModuleType("pyspark")
    pyspark_mod.sql = sql_mod
    monkeypatch.setitem(sys.modules, "pyspark", pyspark_mod)
    monkeypatch.setitem(sys.modules, "pyspark.sql", sql_mod)
    monkeypatch.setitem(sys.modules, "pyspark.sql.types", types_mod)


@entity(schema="dbo", table="every_type", driver=Warehouse)
class EveryType(BaseModel):
    id: Annotated[UUID, Col(pk=True)]
    n: int
    ratio: float
    amount: Annotated[Decimal, Col(precision=12, scale=4)]
    flag: bool
    name: Annotated[str, Col(length=50, name="Name_")]
    at: datetime
    on_day: date
    blob: Annotated[bytes, Col(length=16)]
    note: Annotated[str | None, Col(length=100)] = None


def test_schema_golden(fake_pyspark):
    assert to_spark_schema(EveryType) == StructType(
        [
            StructField("id", StringType(), nullable=False),
            StructField("n", LongType(), nullable=False),
            StructField("ratio", DoubleType(), nullable=False),
            StructField("amount", DecimalType(12, 4), nullable=False),
            StructField("flag", BooleanType(), nullable=False),
            StructField("Name_", StringType(), nullable=False),
            StructField("at", TimestampType(), nullable=False),
            StructField("on_day", DateType(), nullable=False),
            StructField("blob", BinaryType(), nullable=False),
            StructField("note", StringType(), nullable=True),
        ]
    )


def test_decimal_defaults(fake_pyspark):
    @entity(schema="dbo", table="dec_default", driver=Warehouse)
    class DecDefault(BaseModel):
        amount: Decimal

    schema = to_spark_schema(DecDefault)
    assert schema.args[0][0] == StructField("amount", DecimalType(18, 0), nullable=False)


def test_unsupported_type(fake_pyspark):
    @entity(schema="dbo", table="listy", driver=Warehouse)
    class Listy(BaseModel):
        items: list

    with pytest.raises(UnsupportedType, match="unsupported column type list"):
        to_spark_schema(Listy)


def test_missing_pyspark_names_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyspark", None)
    monkeypatch.setitem(sys.modules, "pyspark.sql", None)
    with pytest.raises(ImportError, match=r"fabric-etl\[spark\]"):
        to_spark_schema(EveryType)
