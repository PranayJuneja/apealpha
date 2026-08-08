from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from ..config import settings


class SourceError(RuntimeError):
    """A source could not answer. Carries the source name for health reporting."""

    def __init__(self, source: str, detail: str) -> None:
        super().__init__(f"{source}: {detail}")
        self.source = source
        self.detail = detail


class SourceUnavailable(SourceError):
    """The source is not configured — a missing credential, not a failure."""


_RETRY_STATUS = {429, 500, 502, 503, 504}


class ResponseCache:
    """Small in-process TTL cache.

    Source data is point-in-time, so entries are keyed by the full request and
    expire quickly. This exists to keep a single research run from hitting the
    same endpoint repeatedly, not to serve stale data across runs.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > self._ttl:
            self._entries.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._entries[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._entries.clear()


_cache: ResponseCache | None = None


def cache() -> ResponseCache:
    global _cache
    if _cache is None:
        _cache = ResponseCache(settings().cache_ttl_seconds)
    return _cache


async def request_json(
    source: str,
    url: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
    json_body: Any | None = None,
    auth: tuple[str, str] | None = None,
    attempts: int = 3,
    use_cache: bool = True,
    timeout_seconds: float | None = None,
) -> Any:
    """Fetch JSON with bounded retries on transient failures.

    Raises SourceError on any outcome the caller cannot use, so the engine can
    record one source as degraded without failing the whole run.
    """
    config = settings()
    cache_key = f"{method}|{url}|{sorted((params or {}).items())}|{sorted((data or {}).items())}"
    if use_cache and method == "GET":
        cached = cache().get(cache_key)
        if cached is not None:
            return cached

    last_detail = "no attempt completed"
    timeout = timeout_seconds if timeout_seconds is not None else config.request_timeout_seconds
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for attempt in range(attempts):
            try:
                response = await client.request(
                    method, url, params=params, headers=headers, data=data, json=json_body, auth=auth
                )
            except httpx.HTTPError as exc:
                last_detail = f"transport error ({type(exc).__name__})"
            else:
                if response.status_code in _RETRY_STATUS:
                    last_detail = f"HTTP {response.status_code}"
                elif response.status_code >= 400:
                    raise SourceError(source, f"HTTP {response.status_code}")
                else:
                    try:
                        payload = response.json()
                    except ValueError as exc:
                        raise SourceError(source, "response was not JSON") from exc
                    if use_cache and method == "GET":
                        cache().set(cache_key, payload)
                    return payload
            if attempt < attempts - 1:
                await asyncio.sleep(0.4 * (2**attempt))
    raise SourceError(source, last_detail)


async def request_text(
    source: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 3,
) -> str:
    """Fetch a text body. Used for CSV endpoints that have no JSON surface."""
    config = settings()
    last_detail = "no attempt completed"
    async with httpx.AsyncClient(timeout=config.request_timeout_seconds, follow_redirects=True) as client:
        for attempt in range(attempts):
            try:
                response = await client.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:
                last_detail = f"transport error ({type(exc).__name__})"
            else:
                if response.status_code in _RETRY_STATUS:
                    last_detail = f"HTTP {response.status_code}"
                elif response.status_code >= 400:
                    raise SourceError(source, f"HTTP {response.status_code}")
                else:
                    return response.text
            if attempt < attempts - 1:
                await asyncio.sleep(0.4 * (2**attempt))
    raise SourceError(source, last_detail)
