"""Col annotation and column introspection over pydantic models."""

from __future__ import annotations

import types
import typing
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Col:
    """Column metadata a Python type cannot express. SQL type strings are
    forbidden here — `native` is the only per-driver escape hatch.

    Attributes:
        length: varchar(n) / varbinary(n) length.
        precision: decimal precision (defaults to 18 when rendered).
        scale: decimal scale (defaults to 0 when rendered).
        nullable: explicit override; otherwise nullability comes from ``T | None``.
        default: column default, documentation only.
        pk: primary key member; composite PK order = field declaration order.
        fk: single-column foreign key as ``"schema.table.column"``.
        name: physical column name when it differs from the attribute.
        native: per-driver rendered type, e.g. ``{"warehouse": "varbinary(16)"}``.
        path: XML XPath / dotted JSON path for source entities.
    """

    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    nullable: bool | None = None
    default: Any = None
    pk: bool = False
    fk: str | None = None  # "schema.table.column"
    name: str | None = None  # physical name if != attribute
    native: dict[str, str] | None = None  # {"warehouse": "varbinary(16)"}
    path: str | None = None  # XML XPath / dotted JSON path (source entities)


@dataclass(frozen=True)
class ColumnInfo:
    """One introspected model field.

    Attributes:
        attr: Python attribute name.
        physical: ``col.name`` or ``attr``.
        py_type: unwrapped type (``T | None`` stripped to ``T``).
        optional: whether the annotation was ``T | None``.
        col: the ``Col`` annotation (default ``Col()`` if none given).
        description: from ``Field(description=...)``.
    """

    attr: str
    physical: str
    py_type: type
    optional: bool
    col: Col
    description: str | None


def _unwrap(annotation: Any) -> tuple[type, bool]:
    """Strip `T | None` / Optional[T]; return (inner type, was optional)."""
    if typing.get_origin(annotation) in (types.UnionType, typing.Union):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
    return annotation, False


def columns(cls: type) -> list[ColumnInfo]:
    """ColumnInfo per model field, in declaration order.

    Args:
        cls: a pydantic model class.

    Returns:
        One ``ColumnInfo`` per field, ``Col`` annotations resolved.
    """
    out: list[ColumnInfo] = []
    for attr, field in cls.model_fields.items():
        col = next((m for m in field.metadata if isinstance(m, Col)), Col())
        py_type, optional = _unwrap(field.annotation)
        out.append(
            ColumnInfo(
                attr=attr,
                physical=col.name or attr,
                py_type=py_type,
                optional=optional,
                col=col,
                description=field.description,
            )
        )
    return out
