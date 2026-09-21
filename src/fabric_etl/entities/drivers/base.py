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

    @classmethod
    def _quote(cls, name: str) -> str:
        return name

    @classmethod
    def _qualify(cls, dotted: str) -> str:
        return ".".join(cls._quote(p) for p in dotted.split("."))

    @classmethod
    def _column_lines(cls, info: EntityInfo) -> list[str]:
        return [
            f"{cls._quote(c.physical)} {cls.render(c.py_type, c.col)}"
            f" {'NULL' if cls.nullable(c) else 'NOT NULL'}"
            for c in info.columns
        ]

    @classmethod
    def _fk_lines(cls, info: EntityInfo, suffix: str = "") -> list[str]:
        lines = []
        for c in info.columns:
            if c.col.fk:  # "schema.table.column"
                table, _, ref_col = c.col.fk.rpartition(".")
                lines.append(
                    f"FOREIGN KEY ({cls._quote(c.physical)}) REFERENCES"
                    f" {cls._qualify(table)} ({cls._quote(ref_col)}){suffix}"
                )
        by_attr = {c.attr: c for c in info.columns}
        for attrs, ref in info.fks.items():  # {("a", "b"): "s.t.(x,y)"}
            table, _, cols_part = ref.partition(".(")
            ref_cols = [r.strip() for r in cols_part.rstrip(")").split(",")]
            local = ", ".join(cls._quote(by_attr[a].physical) for a in attrs)
            remote = ", ".join(cls._quote(r) for r in ref_cols)
            lines.append(
                f"FOREIGN KEY ({local}) REFERENCES {cls._qualify(table)} ({remote}){suffix}"
            )
        return lines

    @classmethod
    def _create_table(cls, info: EntityInfo, lines: list[str], **params: Any) -> str:
        body = ",\n    ".join(lines)
        return f"CREATE TABLE {cls.full_name(info, **params)} (\n    {body}\n)"
