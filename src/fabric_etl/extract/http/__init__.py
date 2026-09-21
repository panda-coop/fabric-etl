"""HTTP extraction for REST sources. Requires the [http] extra."""

try:
    import httpx  # noqa: F401
except ImportError as exc:
    raise ImportError("fabric_etl.extract.http requires httpx — install fabric-etl[http]") from exc

from fabric_etl.extract.http.client import RETRY_STATUSES, Client

__all__ = ["RETRY_STATUSES", "Client"]
