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
    """One change-table row: operation, LSN position, and the typed payload."""

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
    from_lsn None starts at the capture instance's minimum LSN."""
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
