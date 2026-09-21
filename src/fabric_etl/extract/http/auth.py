"""Auth strategies as httpx.Auth. Callers resolve secrets first and pass plain values in."""

from __future__ import annotations

from collections.abc import Callable, Generator

import httpx


class Basic(httpx.BasicAuth):
    """HTTP basic auth."""


class Bearer(httpx.Auth):
    """Bearer token; a zero-arg callable is re-evaluated per request."""

    def __init__(self, token_or_provider: str | Callable[[], str]) -> None:
        self._token = token_or_provider

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        token = self._token() if callable(self._token) else self._token
        request.headers["Authorization"] = f"Bearer {token}"
        yield request


class ClientCredentials(httpx.Auth):
    """OAuth2 client-credentials flow: cached token, one refresh-and-replay on 401."""

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str | None = None,
    ) -> None:
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self._token: str | None = None

    def _fetch_token(self) -> str:
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.scope is not None:
            data["scope"] = self.scope
        resp = httpx.post(self.token_url, data=data)
        resp.raise_for_status()
        return resp.json()["access_token"]

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        if self._token is None:
            self._token = self._fetch_token()
        request.headers["Authorization"] = f"Bearer {self._token}"
        response = yield request
        if response.status_code == 401:
            self._token = self._fetch_token()
            request.headers["Authorization"] = f"Bearer {self._token}"
            yield request


class QueryAuth(httpx.Auth):
    """Credentials appended to every request's query string (legacy B2B vendors).

    https is enforced — credentials never travel over plain http. The param
    names in .masked are hidden by the client's log hook.
    """

    def __init__(self, params: dict[str, str]) -> None:
        self._params = dict(params)
        self.masked: frozenset[str] = frozenset(self._params)

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        if request.url.scheme != "https":
            raise ValueError(f"QueryAuth requires https, got {request.url.scheme}://")
        request.url = request.url.copy_merge_params(self._params)
        yield request
