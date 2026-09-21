import importlib
import sys

import httpx
import pytest
import respx

from fabric_etl.extract.http import Client
from fabric_etl.extract.http import client as client_mod


@respx.mock
def test_request_ok():
    respx.get("https://feed.example/x").respond(200, text="ok")
    with Client() as c:
        assert c.get("https://feed.example/x").text == "ok"


@respx.mock
def test_retries_retryable_status_then_succeeds():
    route = respx.get("https://feed.example/x")
    route.side_effect = [httpx.Response(503), httpx.Response(200, text="ok")]
    with Client(backoff=0) as c:
        resp = c.get("https://feed.example/x")
    assert resp.text == "ok"
    assert route.call_count == 2


@respx.mock
def test_retries_transport_error_then_succeeds():
    route = respx.get("https://feed.example/x")
    route.side_effect = [httpx.ConnectError("boom"), httpx.Response(200, text="ok")]
    with Client(backoff=0) as c:
        assert c.get("https://feed.example/x").text == "ok"


@respx.mock
def test_exhausted_retries_raise():
    route = respx.get("https://feed.example/x")
    route.respond(503)
    with Client(retries=1, backoff=0) as c, pytest.raises(httpx.HTTPStatusError):
        c.get("https://feed.example/x")
    assert route.call_count == 2


@respx.mock
def test_non_retryable_error_status_raises_immediately():
    route = respx.get("https://feed.example/x")
    route.respond(404)
    with Client(backoff=0) as c, pytest.raises(httpx.HTTPStatusError):
        c.get("https://feed.example/x")
    assert route.call_count == 1


@respx.mock
def test_pages_follows_next_url_until_none():
    respx.get("https://feed.example/items?page=1").respond(
        200, json={"items": [1], "next": "https://feed.example/items?page=2"}
    )
    respx.get("https://feed.example/items?page=2").respond(200, json={"items": [2], "next": None})
    with Client() as c:
        pages = list(
            c.pages(
                "https://feed.example/items",
                params={"page": 1},
                next_url=lambda r: r.json()["next"],
            )
        )
    assert [p.json()["items"] for p in pages] == [[1], [2]]


@respx.mock
def test_log_hook_events_carry_stable_correlation_id():
    respx.get("https://feed.example/a").respond(200)
    respx.get("https://feed.example/b").respond(404)
    events: list[dict] = []
    with Client(retries=0, log_hook=events.append) as c:
        c.get("https://feed.example/a")
        with pytest.raises(httpx.HTTPStatusError):
            c.get("https://feed.example/b")
    assert [e["status"] for e in events] == [200, 404]
    assert events[0]["method"] == "GET"
    assert events[0]["url"] == "https://feed.example/a"
    assert events[0]["elapsed"] >= 0
    ids = {e["correlation_id"] for e in events}
    assert ids == {c.correlation_id} and len(c.correlation_id) == 32


@respx.mock
def test_backoff_sleeps_exponentially(monkeypatch):
    route = respx.get("https://feed.example/x")
    route.side_effect = [httpx.Response(503), httpx.Response(503), httpx.Response(200)]
    sleeps: list[float] = []
    monkeypatch.setattr(client_mod.time, "sleep", sleeps.append)
    with Client(backoff=1.0) as c:
        c.get("https://feed.example/x")
    assert sleeps == [1.0, 2.0]


def test_import_without_httpx_names_extra(monkeypatch):
    for mod in [m for m in list(sys.modules) if m.startswith("fabric_etl.extract.http")]:
        monkeypatch.delitem(sys.modules, mod)
    monkeypatch.setitem(sys.modules, "httpx", None)
    with pytest.raises(ImportError, match=r"fabric-etl\[http\]"):
        importlib.import_module("fabric_etl.extract.http")
