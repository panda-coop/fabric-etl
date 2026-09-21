"""Fabric Lakehouse (Delta) driver: Spark types, optional schema."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fabric_etl.entities.columns import Col
from fabric_etl.entities.drivers.base import Driver
from fabric_etl.entities.entity import resolve

if TYPE_CHECKING:
    from fabric_etl.entities.entity import EntityInfo


class Lakehouse(Driver):
    name = "lakehouse"
    types = {
        int: "long",
        float: "double",
        Decimal: "decimal(p,s)",
        bool: "boolean",
        str: "string",  # length ignored, noted in docs
        datetime: "timestamp",
        date: "date",
        bytes: "binary",
        UUID: "string",
    }

    @classmethod
    def _render(cls, py_type: type, col: Col) -> str:
        if py_type is Decimal:
            return f"decimal({col.precision or 18},{col.scale or 0})"
        return cls.types[py_type]

    @classmethod
    def full_name(cls, info: EntityInfo, **params: Any) -> str:
        table = resolve(info.table, **params)
        if info.schema is None:
            return table
        return f"{resolve(info.schema, **params)}.{table}"

    @classmethod
    def ddl(cls, info: EntityInfo, **params: Any) -> str:
        # Delta has no PK/FK constraints — pk/fks are documentation only here.
        body = ",\n    ".join(cls._column_lines(info))
        return f"CREATE TABLE {cls.full_name(info, **params)} (\n    {body}\n) USING DELTA"
