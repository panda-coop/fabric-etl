"""Row writers: Warehouse over any DB-API 2 connection, Lakehouse over a
Spark DataFrame. No driver package is imported — connections are duck-typed."""

from __future__ import annotations

from collections.abc import Iterable
from itertools import islice
from typing import Any

from fabric_etl.entities.entity import EntityInfo

BATCH_SIZE = 1000


def _row_params(info: EntityInfo, row: Any) -> tuple:
    if isinstance(row, dict):
        return tuple(row[c.attr] for c in info.columns)
    return tuple(getattr(row, c.attr) for c in info.columns)


def _merge_sql(info: EntityInfo, full: str, n_rows: int) -> str:
    cols = [c.physical for c in info.columns]
    pk = [c.physical for c in info.pk]
    row = "(" + ", ".join(["?"] * len(cols)) + ")"
    on = " AND ".join(f"t.{c} = s.{c}" for c in pk)
    sets = ", ".join(f"t.{c} = s.{c}" for c in cols if c not in pk)
    names = ", ".join(cols)
    matched = f" WHEN MATCHED THEN UPDATE SET {sets}" if sets else ""
    return (
        f"MERGE {full} AS t USING (VALUES {', '.join([row] * n_rows)}) AS s ({names})"
        f" ON {on}{matched}"
        f" WHEN NOT MATCHED THEN INSERT ({names})"
        f" VALUES ({', '.join(f's.{c}' for c in cols)});"
    )


def warehouse(entity_cls: type, rows: Iterable[Any], conn: Any, *, merge: bool = False) -> int:
    """Write entity instances or dicts (keyed by attribute) in batches of
    BATCH_SIZE — constant memory. merge=True upserts on the primary key.

    Args:
        entity_cls: the target @entity class.
        rows: model instances or attribute-keyed dicts; consumed lazily.
        conn: any DB-API 2 connection; committed once at the end.
        merge: MERGE on the primary key instead of plain INSERT.

    Returns:
        Rows written.

    Raises:
        ValueError: merge=True on an entity without a primary key.
    """
    info: EntityInfo = entity_cls.__entity__
    full = info.full_name()
    if merge and not info.pk:
        raise ValueError(f"merge requires a primary key: {info.key}")
    names = ", ".join(c.physical for c in info.columns)
    placeholders = ", ".join(["?"] * len(info.columns))
    insert = f"INSERT INTO {full} ({names}) VALUES ({placeholders})"
    cursor = conn.cursor()
    count = 0
    it = iter(rows)
    while batch := [_row_params(info, r) for r in islice(it, BATCH_SIZE)]:
        if merge:
            cursor.execute(_merge_sql(info, full, len(batch)), [v for p in batch for v in p])
        else:
            cursor.executemany(insert, batch)
        count += len(batch)
    conn.commit()
    return count


def lakehouse(entity_cls: type, df: Any, *, mode: str = "append") -> None:
    """Write a Spark DataFrame as a Delta table named by the entity.

    Args:
        entity_cls: the target @entity class (names the Delta table).
        df: the Spark DataFrame to save.
        mode: Spark save mode ("append", "overwrite", ...).
    """
    info: EntityInfo = entity_cls.__entity__
    df.write.format("delta").mode(mode).saveAsTable(info.full_name())
