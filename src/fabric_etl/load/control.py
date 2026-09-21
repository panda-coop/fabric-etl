"""fabric-etl's own operational tables — run log and watermark, dogfooding the
entity layer: declared with @entity exactly like user tables."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import Warehouse


@entity(schema="control", table="run_log", driver=Warehouse)
class RunLog(BaseModel):
    """One row per load run: job, timing, row count, outcome."""

    id: Annotated[UUID, Col(pk=True)]
    job: Annotated[str, Col(length=100)]
    started: datetime
    finished: datetime
    rows: int
    status: Annotated[str, Col(length=20)]
    error: Annotated[str | None, Col(length=4000)] = None


@entity(schema="control", table="watermark", driver=Warehouse)
class Watermark(BaseModel):
    """Last processed position per job (LSN hex, timestamp, id — as a string)."""

    job: Annotated[str, Col(length=100, pk=True)]
    value: Annotated[str, Col(length=200)]
    updated: datetime
