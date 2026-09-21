"""Driver base: per-platform type rendering, full names, DDL. Pure — no DB deps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fabric_etl.entities.columns import Col, ColumnInfo

if TYPE_CHECKING:
    from fabric_etl.entities.entity import EntityInfo


class UnsupportedType(ValueError):
    """A driver cannot render this Python type / Col combination."""


class Driver:
    """All-classmethod, never instantiated. `types` is the public supported-type
    contract (docs emit it); `render` substitutes Col parameters into it."""

    name: str
    types: dict[type, str]

    @classmethod
    def render(cls, py_type: type, col: Col) -> str:
        if col.native and cls.name in col.native:
            return col.native[cls.name]
        if py_type not in cls.types:
            supported = ", ".join(t.__name__ for t in cls.types)
            raise UnsupportedType(
                f"{cls.name}: unsupported column type {py_type.__name__}; supported: {supported}"
            )
        return cls._render(py_type, col)

    @classmethod
    def _render(cls, py_type: type, col: Col) -> str:
        raise NotImplementedError

    @staticmethod
    def nullable(column: ColumnInfo) -> bool:
        if column.col.nullable is not None:
            return column.col.nullable
        return column.optional

    @classmethod
    def full_name(cls, info: EntityInfo, **params: Any) -> str:
        raise NotImplementedError

    @classmethod
    def ddl(cls, info: EntityInfo, **params: Any) -> str:
        raise NotImplementedError
