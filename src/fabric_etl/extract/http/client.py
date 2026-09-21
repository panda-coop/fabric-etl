"""Retrying sync httpx client for REST sources. Sync only — Fabric notebooks are sync callers."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterator

import httpx

# Statuses worth retrying: throttling + transient upstream failures.
RETRY_STATUSES = (429, 502, 503, 504)


class Client:
    """httpx.Client wrapper: retry with exponential backoff, pagination, request logging.

    log_hook(event: dict) is called once per received response with method, url,
    status, elapsed and a per-Client correlation_id.
    """

    def __init__(
        self,
        base_url: str = "",
        *,
        auth: httpx.Auth | None = None,
        timeout: float = 30.0,
        headers: dict | None = None,
        retries: int = 3,
        backoff: float = 1.0,
        log_hook: Callable[[dict], None] | None = None,
    ) -> None:
        self.retries = retries
        self.backoff = backoff
        self.log_hook = log_hook
        self.correlation_id = uuid.uuid4().hex
        # QueryAuth exposes .masked — those query params are hidden in log events.
        self._masked: frozenset[str] = frozenset(getattr(auth, "masked", ()))
        self._client = httpx.Client(
            base_url=base_url,
            auth=auth,
            timeout=timeout,
            headers=headers,
            follow_redirects=True,
        )

    def __enter__(self) -> Client:
        self._client.__enter__()
        return self

    def __exit__(self, *exc_info) -> None:
        self._client.__exit__(*exc_info)

    def close(self) -> None:
        self._client.close()

    def request(self, method: str, url: str, **kw) -> httpx.Response:
        """Issue a request, retrying transport errors and retryable statuses.

        Backoff is exponential (backoff * 2**attempt). Raises the last error /
        the final response's raise_for_status() when retries are exhausted.
        """
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = self._client.request(method, url, **kw)
            except httpx.TransportError as exc:
                last_exc = exc
            else:
                self._log(resp)
                if resp.status_code not in RETRY_STATUSES:
                    resp.raise_for_status()
                    return resp
                last_exc = httpx.HTTPStatusError(
                    f"retryable status {resp.status_code}", request=resp.request, response=resp
                )
            if attempt < self.retries:
                time.sleep(self.backoff * 2**attempt)
        raise last_exc  # type: ignore[misc]  # loop always sets it before falling through

    def get(self, url: str, **kw) -> httpx.Response:
        return self.request("GET", url, **kw)

    def pages(
        self,
        url: str,
        *,
        params: dict | None = None,
        next_url: Callable[[httpx.Response], str | None],
    ) -> Iterator[httpx.Response]:
        """Follow pagination: yield the first page, then next_url(response) until None."""
        resp = self.get(url, params=params)
        yield resp
        while (nxt := next_url(resp)) is not None:
            resp = self.get(nxt)
            yield resp

    def _log(self, resp: httpx.Response) -> None:
        if self.log_hook is None:
            return
        self.log_hook(
            {
                "method": resp.request.method,
                "url": self._mask(resp.request.url),
                "status": resp.status_code,
                "elapsed": resp.elapsed.total_seconds(),
                "correlation_id": self.correlation_id,
            }
        )

    def _mask(self, url: httpx.URL) -> str:
        replaced = {k: "***" for k in self._masked if k in url.params}
        if replaced:
            url = url.copy_merge_params(replaced)
        return str(url)
