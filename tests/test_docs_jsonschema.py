"""Tests for docs.jsonschema."""

import json
from typing import Annotated

from pydantic import BaseModel, Field

from fabric_etl.docs import jsonschema
from fabric_etl.entities import Col, Registry, entity
from fabric_etl.entities.drivers import Warehouse


@entity(schema="dbo", table="sales_line", driver=Warehouse)
class BronzeSalesLine(BaseModel):
    tenant: Annotated[str, Col(length=4, pk=True)]
    amount: int = Field(description="Line amount")


@entity(driver=Warehouse)
class Dim(BaseModel):
    code: Annotated[str, Col(length=10, pk=True)]


def _registry() -> Registry:
    r = Registry()
    r.register(BronzeSalesLine.__entity__)
    r.register(Dim.__entity__)
    return r


def test_paths_and_valid_json():
    out = jsonschema.emit(_registry())
    assert set(out) == {"dbo/sales_line.schema.json", "_noschema/dim.schema.json"}
    schema = json.loads(out["dbo/sales_line.schema.json"])
    assert schema["title"] == "BronzeSalesLine"
    assert set(schema["properties"]) == {"tenant", "amount"}
    assert schema["properties"]["amount"]["description"] == "Line amount"


def test_sorted_keys_and_deterministic():
    r = _registry()
    out = jsonschema.emit(r)
    content = out["dbo/sales_line.schema.json"]
    assert content == json.dumps(json.loads(content), indent=2, sort_keys=True) + "\n"
    assert out == jsonschema.emit(r)
