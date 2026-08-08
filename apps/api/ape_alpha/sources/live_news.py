from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Awaitable
from urllib.parse import urlparse

from ..config import settings
from ..markets import MarketProfile
from .http import SourceError, SourceUnavailable
from .webcmd import invoke_json


@dataclass(frozen=True)
class ProviderFetch:
    provider: str
    articles: list[dict[str, Any]]


@dataclass(frozen=True)
class NewsFetch:
    articles: list[dict[str, Any]]
    provider: str
    detail: str


def _created_at(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _normalize(row: dict[str, Any]) -> dict[str, Any] | None:
    title = str(row.get("title", "") or "").strip()
    url = str(row.get("url", "") or "").strip()
    created_at = _created_at(row.get("createdAt"))
    if not title or not url.startswith("https://") or created_at is None:
        return None
    publisher = str(row.get("publisher", "") or "").strip()
    provider = str(row.get("provider", "") or "webcmd-news").strip()
    return {
        "title": title,
        "url": url,
        "domain": (publisher or urlparse(url).netloc).lower(),
        "language": str(row.get("language", "en-US") or "en-US"),
        "country": str(row.get("country", "US") or "US"),
        "created_at": created_at,
        "provider": provider,
    }


async def _command(
    name: str,
    ticker: str,
    company: str,
    args: tuple[str, ...],
) -> ProviderFetch:
    provider = f"webcmd-{name}"
    payload = await invoke_json(
        ("ape-alpha", name, company, "--ticker", ticker, *args, "-f", "json"),
        source=provider,
        timeout=settings().webcmd_timeout_seconds,
    )
    if not isinstance(payload, list):
        raise SourceError(provider, "search returned an unsupported shape")
    articles = [normalized for row in payload if isinstance(row, dict) if (normalized := _normalize(row))]
    return ProviderFetch(provider, articles)


async def _google(ticker: str, company: str, profile: MarketProfile, limit: int) -> ProviderFetch:
    language, country, ceid = profile.news_locale
    return await _command(
        "google-news",
        ticker,
        company,
        (
            "--language",
            language,
            "--country",
            country,
            "--ceid",
            ceid,
            "--limit",
            str(limit),
        ),
    )


async def _yahoo(ticker: str, company: str, limit: int) -> ProviderFetch:
    return await _command("yahoo-news", ticker, company, ("--limit", str(limit),))


async def fetch_articles(
    ticker: str,
    company: str,
    profile: MarketProfile,
    *,
    limit: int = 100,
) -> NewsFetch:
    """Fetch current Google and Yahoo coverage through WebCMD for every run.

    Either provider is sufficient for live current-news coverage. Partial
    failures remain visible in the detail string, and no direct HTTP fallback
    silently bypasses the user's requested WebCMD acquisition path.
    """
    calls: list[Awaitable[ProviderFetch]] = [
        _google(ticker, company, profile, limit),
        _yahoo(ticker, company, min(limit, 50)),
    ]
    fetched = await asyncio.gather(*calls, return_exceptions=True)
    live = [item for item in fetched if isinstance(item, ProviderFetch)]
    failures = [item for item in fetched if isinstance(item, BaseException)]
    if not live:
        detail = "; ".join(
            f"{getattr(item, 'source', 'webcmd-news')}: {getattr(item, 'detail', type(item).__name__)}"
            for item in failures
        ) or "no WebCMD news provider was available"
        if failures and all(isinstance(item, SourceUnavailable) for item in failures):
            raise SourceUnavailable("webcmd-news", detail)
        raise SourceError("webcmd-news", detail)

    merged: dict[str, dict[str, Any]] = {}
    for outcome in live:
        for article in outcome.articles:
            key = f"{article['title'].strip().lower()}|{article['created_at'].date().isoformat()}"
            merged.setdefault(key, article)
    articles = sorted(merged.values(), key=lambda item: item["created_at"])
    live_detail = ", ".join(f"{item.provider} {len(item.articles)}" for item in live)
    failure_detail = "; ".join(
        f"{getattr(item, 'source', 'webcmd-news')} unavailable: {getattr(item, 'detail', type(item).__name__)}"
        for item in failures
    )
    return NewsFetch(
        articles=articles,
        provider=" + ".join(item.provider for item in live),
        detail="; ".join(part for part in (live_detail, failure_detail) if part),
    )
