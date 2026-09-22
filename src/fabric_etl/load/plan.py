"""Drift plan against INFORMATION_SCHEMA. Exactly three outcomes — create,
add_column, recreate: Warehouse has effectively no ALTER COLUMN, so type or
nullability changes and column drops are never automated."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fabric_etl.entities.entity import EntityInfo, Registry, resolve
from fabric_etl.load.ddl import ddl

_TABLES_SQL = (
    "SELECT table_name FROM INFORMATION_SCHEMA.TABLES WHERE table_schema = ? AND table_name = ?"
)
_COLUMNS_SQL = (
    "SELECT column_name, is_nullable, data_type, character_maximum_length,"
    " numeric_precision, numeric_scale FROM INFORMATION_SCHEMA.COLUMNS"
    " WHERE table_schema = ? AND table_name = ?"
)
_TYPE = re.compile(r"^(\w+)(?:\((\d+)(?:,\s*(\d+))?\))?$")


@dataclass(frozen=True)
class PlanAction:
    """One drift action.

    Attributes:
        kind: "create" (with the CREATE TABLE statement as detail),
            "add_column" (an ALTER TABLE ... ADD statement) or
            "recreate" (human-readable reasons — the rebuild is manual).
        entity: the drifting entity.
        detail: statement or reasons, per kind.
    """

    kind: str  # "create" | "add_column" | "recreate"
    entity: EntityInfo
    detail: str


def _type_mismatch(rendered: str, data_type: str, char_len: Any, prec: Any, scale: Any) -> bool:
    """Loose compare of a rendered type against INFORMATION_SCHEMA columns:
    base name always; length for char/binary, precision/scale for decimal."""
    m = _TYPE.match(rendered.lower())
    if m is None:  # native escape hatch we cannot parse — base-name compare only
        return rendered.lower() != str(data_type).lower()
    base, arg1, arg2 = m.group(1), m.group(2), m.group(3)
    if base != str(data_type).lower():
        return True
    if base in ("varchar", "char", "varbinary", "binary") and arg1 is not None:
        return char_len != int(arg1)
    if base in ("decimal", "numeric") and arg1 is not None:
        return prec != int(arg1) or scale != int(arg2 or 0)
    return False


def plan(registry: Registry, conn: Any, **params: Any) -> list[PlanAction]:
    """Diff every non-source entity against the live INFORMATION_SCHEMA.

    Type comparison is deliberately loose: base name always, length for
    char/binary, precision/scale for decimal. Entities whose ``{placeholder}``s
    are not satisfied by params are skipped — not bound to a physical table.

    Args:
        registry: entities to check.
        conn: any DB-API 2 connection to the target database.
        **params: values for ``{placeholder}``s in schema/table names.

    Returns:
        Actions in registry order; empty means no drift.
    """
    actions: list[PlanAction] = []
    cursor = conn.cursor()
    for info in registry.entities():
        if info.source:
            continue
        try:
            schema = resolve(info.schema, **params) if info.schema else info.schema
            table = resolve(info.table, **params)
        except KeyError:
            continue  # unresolved {placeholders} — not bound to a physical table

        cursor.execute(_TABLES_SQL, (schema, table))
        if not cursor.fetchall():
            actions.append(PlanAction("create", info, ddl(info, **params)))
            continue

        cursor.execute(_COLUMNS_SQL, (schema, table))
        db_cols = {row[0]: row for row in cursor.fetchall()}
        full = info.full_name(**params)
        adds: list[PlanAction] = []
        reasons: list[str] = []
        for c in info.columns:
            rendered = info.driver.render(c.py_type, c.col)
            row = db_cols.pop(c.physical, None)
            if row is None:
                detail = f"ALTER TABLE {full} ADD {c.physical} {rendered}"
                adds.append(PlanAction("add_column", info, detail))
                continue
            _, is_nullable, data_type, char_len, prec, scale = row
            if _type_mismatch(rendered, data_type, char_len, prec, scale):
                reasons.append(f"column {c.physical}: {data_type} in database vs {rendered}")
            elif (is_nullable == "YES") != info.driver.nullable(c):
                reasons.append(
                    f"column {c.physical}: nullability differs"
                    f" (database {'NULL' if is_nullable == 'YES' else 'NOT NULL'})"
                )
        reasons.extend(f"extra column {name} in database" for name in db_cols)
        if reasons:  # no ALTER COLUMN / DROP COLUMN — the table must be rebuilt
            actions.append(PlanAction("recreate", info, "; ".join(reasons)))
        else:
            actions.extend(adds)
    return actions
