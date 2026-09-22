"""SQL Server CDC extractor: typed change envelopes from any DB-API 2 connection."""

from __future__ import annotations

import re
from collections.abc import Iterator
from enum import IntEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from fabric_etl.entities.entity import resolve

T = TypeVar("T")

_SANITIZE = re.compile(r"[^0-9A-Za-z]")


class CdcOperation(IntEnum):
    """__$operation values of cdc.fn_cdc_get_all_changes_* with N'all update old'."""

    DELETE = 1
    INSERT = 2
    UPDATE_BEFORE = 3
    UPDATE_AFTER = 4


class Cdc(BaseModel, Generic[T]):
    """One change-table row: operation, LSN position, and the typed payload.

    Attributes:
        operation: what happened to the row (update rows come in before/after pairs).
        start_lsn: transaction LSN — the incremental-load position.
        seqval: order within the transaction.
        row: the entity model built from the captured columns.
    """

    operation: CdcOperation
    start_lsn: bytes
    seqval: bytes
    row: T


def capture_instance(entity_cls: type, **params: Any) -> str:
    """SQL Server's default capture-instance name: schema_table with every
    non-alphanumeric character replaced by underscore."""
    info = entity_cls.__entity__
    name = "_".join(p for p in (info.schema, info.table) if p)
    return _SANITIZE.sub("_", resolve(name, **params))


def max_lsn(conn: Any) -> bytes:
    """Current database high watermark."""
    cursor = conn.cursor()
    cursor.execute("SELECT sys.fn_cdc_get_max_lsn()")
    return cursor.fetchone()[0]


def changes(
    entity_cls: type,
    conn: Any,
    from_lsn: bytes | None,
    to_lsn: bytes,
    *,
    instance: str | None = None,
    **params: Any,
) -> Iterator[Cdc[Any]]:
    """Stream typed change envelopes from cdc.fn_cdc_get_all_changes_<instance>,
    one fetchmany batch at a time. N'all update old' includes update-before rows.
    from_lsn None starts at the capture instance's minimum LSN.

    Args:
        entity_cls: the @entity class describing the captured table.
        conn: any DB-API 2 connection to the source database.
        from_lsn: window start (inclusive), or None for the capture minimum.
        to_lsn: window end (inclusive), usually :func:`max_lsn`.
        instance: capture-instance override; defaults to :func:`capture_instance`.
        **params: values for ``{placeholder}``s in the table name.

    Yields:
        ``Cdc[model]`` envelopes ordered by (start_lsn, seqval).
    """
    info = entity_cls.__entity__
    instance = instance or capture_instance(entity_cls, **params)
    cursor = conn.cursor()
    if from_lsn is None:
        cursor.execute("SELECT sys.fn_cdc_get_min_lsn(?)", (instance,))
        from_lsn = cursor.fetchone()[0]
    cols = ", ".join(f"[{c.physical}]" for c in info.columns)  # CDC is SQL Server: brackets
    cursor.execute(
        f"SELECT __$operation, __$start_lsn, __$seqval, {cols}"
        f" FROM cdc.fn_cdc_get_all_changes_{instance}(?, ?, N'all update old')"
        " ORDER BY __$start_lsn, __$seqval",
        (from_lsn, to_lsn),
    )
    envelope = Cdc[info.cls]
    attrs = [c.attr for c in info.columns]
    while rows := cursor.fetchmany(cursor.arraysize):
        for row in rows:
            operation, start_lsn, seqval, *values = row
            yield envelope(
                operation=operation,
                start_lsn=start_lsn,
                seqval=seqval,
                row=info.cls.model_validate(dict(zip(attrs, values, strict=True))),
            )


def _watermark_table() -> str:
    from fabric_etl.load.control import Watermark  # lazy: keep extract import-light

    return Watermark.__entity__.full_name()


def get_watermark(conn: Any, job: str) -> bytes | None:
    """Last committed LSN for job from control.watermark (hex-decoded), or None."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT value FROM {_watermark_table()} WHERE job = ?", (job,))
    row = cursor.fetchone()
    return bytes.fromhex(row[0]) if row else None


def set_watermark(conn: Any, job: str, lsn: bytes) -> None:
    """Upsert the job's LSN, hex-encoded; updated is set server-side."""
    cursor = conn.cursor()
    cursor.execute(
        f"MERGE {_watermark_table()} AS t USING (SELECT ? AS job, ? AS value) AS s"
        " ON t.job = s.job"
        " WHEN MATCHED THEN UPDATE SET t.value = s.value, t.updated = SYSUTCDATETIME()"
        " WHEN NOT MATCHED THEN INSERT (job, value, updated)"
        " VALUES (s.job, s.value, SYSUTCDATETIME());",
        (job, lsn.hex()),
    )
    conn.commit()


def window(
    entity_cls: type,
    conn: Any,
    *,
    job: str,
    instance: str | None = None,
    **params: Any,
) -> Iterator[Cdc[Any]]:
    """One incremental pass: changes from the job's watermark (capture minimum
    on first run) up to the current max LSN. The watermark advances to that max
    only after full consumption — a partially consumed iterator leaves it
    untouched, so a re-run replays the same window.

    Args:
        entity_cls: the @entity class describing the captured table.
        conn: any DB-API 2 connection to the source database.
        job: watermark key in control.watermark.
        instance: capture-instance override; defaults to :func:`capture_instance`.
        **params: values for ``{placeholder}``s in the table name.

    Yields:
        ``Cdc[model]`` envelopes for the window, ordered by (start_lsn, seqval).
    """
    from_lsn = get_watermark(conn, job)
    to_lsn = max_lsn(conn)
    yield from changes(entity_cls, conn, from_lsn, to_lsn, instance=instance, **params)
    set_watermark(conn, job, to_lsn)
