from typing import Annotated

import pytest
import respx
from pydantic import BaseModel

from fabric_etl.entities import Col, entity
from fabric_etl.entities.drivers import Http
from fabric_etl.extract.http import Client, http


@entity(
    driver=Http,
    source=True,
    endpoint="https://api.example.com/v1/{tenant}/items",
    items="data.items",
)
class ApiItem(BaseModel):
    id: int
    code: Annotated[str, Col(path="sku")]
    qty: Annotated[int, Col(path="stock.qty")]


@entity(driver=Http, source=True, endpoint="https://api.example.com/v1/flat")
class ApiFlat(BaseModel):
    id: int


@entity(driver=Http, source=True, endpoint="https://api.example.com/v1/single", items="data")
class ApiSingle(BaseModel):
    id: int


@respx.mock
def test_typed_models_with_paths_and_placeholder():
    respx.get("https://api.example.com/v1/ho00/items").respond(
        200,
        json={
            "data": {
                "items": [
                    {"id": 1, "sku": "A-1", "stock": {"qty": 5}},
                    {"id": 2, "sku": "B-2", "stock": {"qty": 0}},
                ]
            }
        },
    )
    with Client() as c:
        rows = list(http(ApiItem, c, tenant="ho00"))
    assert [type(r) for r in rows] == [ApiItem, ApiItem]
    assert [(r.id, r.code, r.qty) for r in rows] == [(1, "A-1", 5), (2, "B-2", 0)]


@respx.mock
def test_items_none_takes_payload_root_list():
    respx.get("https://api.example.com/v1/flat").respond(200, json=[{"id": 1}, {"id": 2}])
    with Client() as c:
        assert [r.id for r in http(ApiFlat, c)] == [1, 2]


@respx.mock
def test_items_dict_is_a_single_record():
    respx.get("https://api.example.com/v1/single").respond(200, json={"data": {"id": 7}})
    with Client() as c:
        rows = list(http(ApiSingle, c))
    assert [r.id for r in rows] == [7]


@respx.mock
def test_items_path_not_a_list_raises():
    respx.get("https://api.example.com/v1/ho00/items").respond(
        200, json={"data": {"items": "oops"}}
    )
    with Client() as c, pytest.raises(ValueError, match="data.items"):
        list(http(ApiItem, c, tenant="ho00"))


def test_non_entity_class_raises_type_error():
    class Plain(BaseModel):
        id: int

    with Client() as c, pytest.raises(TypeError, match="__entity__"):
        list(http(Plain, c))
