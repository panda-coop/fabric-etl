"""Tests for load.ddl — the caller-side wrapper over driver DDL."""

from typing import Annotated

import pytest
from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import Lakehouse, Warehouse
from fabric_etl.load.ddl import ddl


@entity(schema="dbo", table="thing", driver=Warehouse)
class Thing(BaseModel):
    id: Annotated[int, Col(pk=True)]
    name: Annotated[str, Col(length=50)]


@entity(schema="dbo", table="src_{company}", driver=Warehouse, source=True)
class SourceThing(BaseModel):
    x: Annotated[str, Col(length=10, pk=True)]


@entity(schema="dbo", table="orphan")
class Orphan(BaseModel):
    id: Annotated[int, Col(pk=True)]


def test_delegates_to_info_driver():
    assert ddl(Thing) == Warehouse.ddl(Thing.__entity__)


def test_accepts_entity_info():
    assert ddl(Thing.__entity__) == ddl(Thing)


def test_driver_override():
    assert ddl(Thing, driver=Lakehouse) == Lakehouse.ddl(Thing.__entity__)


def test_params_forwarded():
    @entity(schema="dbo", table="t_{company}", driver=Warehouse)
    class Placeholdered(BaseModel):
        id: Annotated[int, Col(pk=True)]

    assert "dbo.t_ho00" in ddl(Placeholdered, company="ho00")


def test_source_entity_refused():
    with pytest.raises(ValueError, match="source entities have no DDL"):
        ddl(SourceThing)


def test_no_driver_is_an_error():
    with pytest.raises(ValueError, match="has no driver"):
        ddl(Orphan)
