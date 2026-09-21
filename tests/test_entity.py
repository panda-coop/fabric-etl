"""Tests for entities.entity."""

from typing import Annotated

import pytest
from pydantic import BaseModel

from fabric_etl.entities import REGISTRY, Col, entity
from fabric_etl.entities.entity import resolve


class FakeDriver:
    name = "fake"

    @classmethod
    def full_name(cls, info, **params):
        return resolve(info.table, **params)


@entity(schema="dbo", description="explicit wins")
class BronzeSalesLine(BaseModel):
    """Docstring, unused here."""

    tenant: Annotated[str, Col(length=4, pk=True)]
    line_no: Annotated[int, Col(pk=True)]


@entity()
class SilverOrder(BaseModel):
    """Silver order, one row per order."""

    order_id: int


def test_registration_key():
    key = f"{BronzeSalesLine.__module__}.BronzeSalesLine"
    assert BronzeSalesLine.__entity__.key == key
    assert REGISTRY.get(key) is BronzeSalesLine.__entity__


def test_class_returned_unchanged():
    row = BronzeSalesLine(tenant="ho00", line_no=1)
    assert row.line_no == 1
    assert not hasattr(BronzeSalesLine, "full_name")


def test_description_explicit_wins():
    assert BronzeSalesLine.__entity__.description == "explicit wins"


def test_description_docstring_fallback():
    assert SilverOrder.__entity__.description == "Silver order, one row per order."


def test_table_default_snake_case():
    assert BronzeSalesLine.__entity__.table == "bronze_sales_line"
    assert SilverOrder.__entity__.table == "silver_order"


def test_default_schema_from_registry():
    REGISTRY.default_schema = "bronze"

    @entity()
    class Thing(BaseModel):
        x: int

    assert Thing.__entity__.schema == "bronze"


def test_pk_declaration_order():
    assert [c.attr for c in BronzeSalesLine.__entity__.pk] == ["tenant", "line_no"]


def test_entities_sorted_by_key():
    keys = [i.key for i in REGISTRY.entities()]
    assert keys == sorted(keys)


def test_full_name_delegates_and_resolves():
    @entity(table="Cooperative Panda-{company}$Sales Line", driver=FakeDriver, source=True)
    class Erp(BaseModel):
        no: int

    assert Erp.__entity__.full_name(company="HO") == "Cooperative Panda-HO$Sales Line"


def test_full_name_missing_param():
    @entity(table="t_{company}_{year}", driver=FakeDriver)
    class T(BaseModel):
        x: int

    with pytest.raises(KeyError, match=r"\['company', 'year'\].*t_\{company\}_\{year\}"):
        T.__entity__.full_name()


def test_full_name_without_driver():
    @entity()
    class NoDriver(BaseModel):
        x: int

    with pytest.raises(ValueError, match="has no driver"):
        NoDriver.__entity__.full_name()


def test_registry_clear():
    REGISTRY.clear()
    assert REGISTRY.entities() == []
