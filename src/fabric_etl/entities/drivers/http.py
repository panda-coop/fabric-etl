"""HTTP driver: REST sources only — no SQL types, no DDL."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fabric_etl.entities.columns import Col
from fabric_etl.entities.drivers.base import Driver, UnsupportedType
from fabric_etl.entities.entity import resolve

if TYPE_CHECKING:
    from fabric_etl.entities.entity import EntityInfo


class Http(Driver):
    name = "http"
    types: dict[type, str] = {}

    @classmethod
    def render(cls, py_type: type, col: Col) -> str:
        raise UnsupportedType("http: source-only driver, it renders no SQL types")

    @classmethod
    def full_name(cls, info: EntityInfo, **params: Any) -> str:
        if info.endpoint is None:
            raise ValueError(f"http entity {info.key} has no endpoint")
        return resolve(info.endpoint, **params)

    @classmethod
    def ddl(cls, info: EntityInfo, **params: Any) -> str:
        raise UnsupportedType("http: source-only driver, it has no DDL")
