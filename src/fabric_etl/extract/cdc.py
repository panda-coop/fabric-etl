"""SQL Server CDC extractor: typed change envelopes from any DB-API 2 connection."""

from __future__ import annotations

from enum import IntEnum
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


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
