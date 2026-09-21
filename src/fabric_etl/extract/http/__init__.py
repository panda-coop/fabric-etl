"""HTTP extraction for REST sources. Requires the [http] extra."""

from collections.abc import Iterator
from typing import Any, TypeVar

try:
    import httpx  # noqa: F401
except ImportError as exc:
    raise ImportError("fabric_etl.extract.http requires httpx — install fabric-etl[http]") from exc

from pydantic import BaseModel

from fabric_etl.entities.entity import resolve
from fabric_etl.extract.http.auth import Basic, Bearer, ClientCredentials, QueryAuth
from fabric_etl.extract.http.client import RETRY_STATUSES, Client

__all__ = [
    "RETRY_STATUSES",
    "Basic",
    "Bearer",
    "Client",
    "ClientCredentials",
    "QueryAuth",
    "http",
]

M = TypeVar("M", bound=BaseModel)


def _walk(data: Any, path: str | None) -> Any:
    """Follow a dotted path into nested dicts; None/empty path is the value itself."""
    if not path:
        return data
    for part in path.split("."):
        if not isinstance(data, dict):
            return None
        data = data.get(part)
    return data


def http(entity_cls: type[M], client: Client, **params: Any) -> Iterator[M]:
    """GET the entity's endpoint and yield one validated model per record.

    The record list is reached via the entity's dotted `items` path (None means
    the payload root; a dict there is a single record). Column values come from
    each column's Col.path, falling back to its physical name.
    """
    info = getattr(entity_cls, "__entity__", None)
    if info is None:
        raise TypeError(f"{entity_cls.__qualname__} is not an @entity — no __entity__ metadata")
    if info.endpoint is None:
        raise ValueError(f"http entity {info.key} has no endpoint")
    url = resolve(info.endpoint, **params)
    data = client.get(url).json()
    records = _walk(data, info.items)
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise ValueError(f"items path {info.items!r} did not reach a record list in the payload")
    for record in records:
        row = {c.attr: _walk(record, c.col.path or c.physical) for c in info.columns}
        yield entity_cls.model_validate(row)
