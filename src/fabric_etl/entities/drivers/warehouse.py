"""Fabric Warehouse driver: strict types, NOT ENFORCED constraints."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fabric_etl.entities.columns import Col
from fabric_etl.entities.drivers.base import Driver, UnsupportedType
from fabric_etl.entities.entity import resolve

if TYPE_CHECKING:
    from fabric_etl.entities.entity import EntityInfo


class Warehouse(Driver):
    name = "warehouse"
    types = {
        int: "bigint",
        float: "float",
        Decimal: "decimal(p,s)",
        bool: "bit",
        str: "varchar(n)",
        datetime: "datetime2(6)",
        date: "date",
        bytes: "varbinary(n)",
        UUID: "uniqueidentifier",
    }

    @classmethod
    def _render(cls, py_type: type, col: Col) -> str:
        if py_type is Decimal:
            return f"decimal({col.precision or 18},{col.scale or 0})"
        if py_type is str:
            if not col.length:
                raise UnsupportedType(
                    "warehouse: str requires Col(length=...) — nvarchar and varchar(max)"
                    " are not supported in Fabric Warehouse"
                )
            return f"varchar({col.length})"
        if py_type is bytes:
            if not col.length:
                raise UnsupportedType(
                    "warehouse: bytes requires Col(length=...) — varbinary(max)"
                    " is not supported in Fabric Warehouse"
                )
            return f"varbinary({col.length})"
        return cls.types[py_type]

    @classmethod
    def full_name(cls, info: EntityInfo, **params: Any) -> str:
        table = resolve(info.table, **params)
        if info.schema is None:
            return table
        return f"{resolve(info.schema, **params)}.{table}"

    @classmethod
    def ddl(cls, info: EntityInfo, **params: Any) -> str:
        # Warehouse constraints are metadata only: NOT ENFORCED, no identity.
        lines = cls._column_lines(info)
        if info.pk:
            cols = ", ".join(c.physical for c in info.pk)
            lines.append(f"PRIMARY KEY NONCLUSTERED ({cols}) NOT ENFORCED")
        lines.extend(cls._fk_lines(info, suffix=" NOT ENFORCED"))
        return cls._create_table(info, lines, **params)
