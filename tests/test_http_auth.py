import httpx
import pytest
import respx

from fabric_etl.extract.http import Basic, Bearer, Client, ClientCredentials, QueryAuth


@respx.mock
def test_basic_auth_injected():
    route = respx.get("https://feed.example/x").respond(200)
    with Client(auth=Basic("u", "p")) as c:
        c.get("https://feed.example/x")
    assert route.calls.last.request.headers["Authorization"].startswith("Basic ")


@respx.mock
def test_bearer_static_token():
    route = respx.get("https://feed.example/x").respond(200)
    with Client(auth=Bearer("tok")) as c:
        c.get("https://feed.example/x")
    assert route.calls.last.request.headers["Authorization"] == "Bearer tok"


@respx.mock
def test_bearer_provider_reevaluated_per_request():
    route = respx.get("https://feed.example/x").respond(200)
    tokens = iter(["t1", "t2"])
    with Client(auth=Bearer(lambda: next(tokens))) as c:
        c.get("https://feed.example/x")
        c.get("https://feed.example/x")
    sent = [call.request.headers["Authorization"] for call in route.calls]
    assert sent == ["Bearer t1", "Bearer t2"]


@respx.mock
def test_client_credentials_caches_token():
    token_route = respx.post("https://login.example/token").respond(
        200, json={"access_token": "tok1"}
    )
    api = respx.get("https://feed.example/x").respond(200)
    auth = ClientCredentials("https://login.example/token", "cid", "secret", scope="api")
    with Client(auth=auth) as c:
        c.get("https://feed.example/x")
        c.get("https://feed.example/x")
    assert token_route.call_count == 1
    assert all(call.request.headers["Authorization"] == "Bearer tok1" for call in api.calls)
    body = token_route.calls.last.request.content.decode()
    assert "grant_type=client_credentials" in body and "scope=api" in body


@respx.mock
def test_client_credentials_refreshes_on_401_and_replays():
    token_route = respx.post("https://login.example/token")
    token_route.side_effect = [
        httpx.Response(200, json={"access_token": "old"}),
        httpx.Response(200, json={"access_token": "new"}),
    ]
    api = respx.get("https://feed.example/x")
    api.side_effect = [httpx.Response(401), httpx.Response(200, text="ok")]
    auth = ClientCredentials("https://login.example/token", "cid", "secret")
    with Client(auth=auth) as c:
        assert c.get("https://feed.example/x").text == "ok"
    assert token_route.call_count == 2
    assert api.call_count == 2
    assert api.calls.last.request.headers["Authorization"] == "Bearer new"


@respx.mock
def test_query_auth_appends_params_over_https():
    route = respx.get("https://feed.example/x", params={"user": "u", "pass": "s3cret"}).respond(200)
    with Client(auth=QueryAuth({"user": "u", "pass": "s3cret"})) as c:
        c.get("https://feed.example/x")
    assert route.call_count == 1


def test_query_auth_rejects_plain_http():
    with Client(auth=QueryAuth({"pass": "s3cret"})) as c, pytest.raises(ValueError, match="https"):
        c.get("http://feed.example/x")


@respx.mock
def test_query_auth_params_masked_in_log_hook():
    respx.get("https://feed.example/x", params={"user": "u", "pass": "s3cret"}).respond(200)
    events: list[dict] = []
    auth = QueryAuth({"user": "u", "pass": "s3cret"})
    assert auth.masked == frozenset({"user", "pass"})
    with Client(auth=auth, log_hook=events.append) as c:
        c.get("https://feed.example/x")
    url = events[0]["url"]
    assert "s3cret" not in url
    assert "pass=%2A%2A%2A" in url or "pass=***" in url
