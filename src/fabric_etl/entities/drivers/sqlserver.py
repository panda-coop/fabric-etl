"""SQL Server driver: source systems, bracketed names."""

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


class SqlServer(Driver):
    name = "sqlserver"
    types = {
        int: "int",
        float: "float",
        Decimal: "decimal(p,s)",
        bool: "bit",
        str: "nvarchar(n)",
        datetime: "datetime2",
        date: "date",
        bytes: "varbinary(n)",
        UUID: "uniqueidentifier",
    }

    @classmethod
    def _render(cls, py_type: type, col: Col) -> str:
        if py_type is Decimal:
            return f"decimal({col.precision or 18},{col.scale or 0})"
        if py_type is str:
            return f"nvarchar({col.length})" if col.length else "nvarchar(max)"
        if py_type is bytes:
            return f"varbinary({col.length})" if col.length else "varbinary(max)"
        return cls.types[py_type]

    @classmethod
    def full_name(cls, info: EntityInfo, **params: Any) -> str:
        parts = [info.database, info.schema, info.table]
        return ".".join(f"[{resolve(p, **params)}]" for p in parts if p is not None)
