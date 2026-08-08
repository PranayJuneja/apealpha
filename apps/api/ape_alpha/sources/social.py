from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Awaitable

from ..config import settings
from . import reddit
from .http import SourceError, SourceUnavailable
from .naming import company_root
from .webcmd import invoke_json


@dataclass(frozen=True)
class ProviderFetch:
    provider: str
    posts: list[dict[str, Any]]


@dataclass(frozen=True)
class SocialFetch:
    posts: list[dict[str, Any]]
    provider: str
    detail: str


def _created_at(value: Any, *, unknown_is_now: bool = True) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(value)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except (TypeError, ValueError):
                pass
    return datetime.now(UTC) if unknown_is_now else datetime.fromtimestamp(0, tz=UTC)


def _query(ticker: str, company: str) -> str:
    root = company_root(company)
    terms = [f"${ticker}", ticker]
    if root:
        terms.append(f'"{root}"')
    return " OR ".join(terms)


def _explicit_ticker(text: str, ticker: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9])\$?{re.escape(ticker)}(?![A-Za-z0-9])", text, re.IGNORECASE))


def _normalize_reddit(row: dict[str, Any], ticker: str) -> dict[str, Any]:
    body = str(row.get("selftext", "") or "")
    community = str(row.get("subreddit", "") or "").removeprefix("r/")
    return {
        "id": str(row.get("id", "") or ""),
        "ticker": ticker,
        "title": str(row.get("title", "") or "").strip(),
        "body": body,
        "author": str(row.get("author", "") or "[deleted]"),
        "subreddit": community,
        "community": community,
        "platform": "reddit",
        "flair": "",
        "score": int(row.get("score", 0) or 0),
        "comments": int(row.get("comments", 0) or 0),
        "upvote_ratio": 0.5,
        "body_length": len(body),
        "created_at": _created_at(row.get("created_utc"), unknown_is_now=False),
        "url": str(row.get("url", "") or ""),
    }


def _normalize_twitter(row: dict[str, Any], ticker: str) -> dict[str, Any]:
    text = str(row.get("text", "") or "").strip()
    author = str(row.get("author", "") or "unknown").removeprefix("@")
    return {
        "id": str(row.get("id", "") or ""),
        "ticker": ticker,
        "title": text[:280],
        "body": text,
        "author": f"@{author}" if author != "unknown" else author,
        "subreddit": "",
        "community": "X",
        "platform": "x",
        "flair": "",
        "score": int(row.get("likes", 0) or 0),
        "comments": 0,
        "upvote_ratio": 0.5,
        "body_length": len(text),
        "created_at": _created_at(row.get("created_at"), unknown_is_now=False),
        "url": str(row.get("url", "") or ""),
        "views": int(row.get("views", 0) or 0),
        "has_media": bool(row.get("has_media", False)),
    }


async def _reddit_webcmd(
    ticker: str,
    company: str,
    subreddits: tuple[str, ...],
    timeframe: str,
    limit: int,
) -> ProviderFetch:
    payload = await invoke_json(
        (
            "reddit",
            "search",
            _query(ticker, company),
            "--sort",
            "new",
            "--time",
            timeframe,
            "--limit",
            str(limit),
            "-f",
            "json",
        ),
        source="webcmd-reddit",
        timeout=settings().webcmd_timeout_seconds,
    )
    if not isinstance(payload, list):
        raise SourceError("webcmd-reddit", "search returned an unsupported shape")
    posts = [_normalize_reddit(row, ticker) for row in payload if isinstance(row, dict)]
    allowed = {name.lower() for name in subreddits}
    posts = [
        post
        for post in posts
        if post["id"]
        and reddit._mentions_ticker(post, ticker, company)
        and (
            str(post["community"]).lower() in allowed
            or _explicit_ticker(f"{post['title']} {post['body']}", ticker)
        )
    ]
    return ProviderFetch("webcmd-reddit", posts)


async def _reddit_oauth(
    ticker: str,
    company: str,
    subreddits: tuple[str, ...],
    timeframe: str,
    limit: int,
) -> ProviderFetch:
    posts = await reddit.fetch_mentions(
        ticker,
        company,
        subreddits=subreddits,
        timeframe=timeframe,
        limit=limit,
    )
    for post in posts:
        post["platform"] = "reddit"
        post["community"] = post.get("subreddit", "")
    return ProviderFetch("reddit-oauth", posts)


async def _twitter_webcmd(ticker: str, company: str, limit: int) -> ProviderFetch:
    payload = await invoke_json(
        (
            "twitter",
            "search",
            f"{_query(ticker, company)} lang:en",
            "--product",
            "live",
            "--exclude",
            "replies",
            "--limit",
            str(limit),
            "-f",
            "json",
        ),
        source="webcmd-twitter",
        timeout=settings().webcmd_timeout_seconds,
    )
    if not isinstance(payload, list):
        raise SourceError("webcmd-twitter", "search returned an unsupported shape")
    posts = [_normalize_twitter(row, ticker) for row in payload if isinstance(row, dict)]
    posts = [
        post
        for post in posts
        if post["id"] and _explicit_ticker(f"{post['title']} {post['body']}", ticker)
    ]
    return ProviderFetch("webcmd-twitter", posts)


async def _reddit_auto(
    ticker: str,
    company: str,
    subreddits: tuple[str, ...],
    timeframe: str,
    limit: int,
) -> ProviderFetch:
    mode = settings().social_mode
    if mode == "oauth":
        return await _reddit_oauth(ticker, company, subreddits, timeframe, limit)
    if mode not in {"auto", "webcmd"}:
        raise SourceUnavailable("social", f"unsupported APE_SOCIAL_MODE={mode!r}")
    try:
        return await _reddit_webcmd(ticker, company, subreddits, timeframe, limit)
    except (SourceError, SourceUnavailable):
        if mode == "auto" and settings().reddit_enabled:
            return await _reddit_oauth(ticker, company, subreddits, timeframe, limit)
        raise


async def fetch_mentions(
    ticker: str,
    company: str,
    *,
    subreddits: tuple[str, ...],
    timeframe: str = "week",
    limit: int = 100,
) -> SocialFetch:
    """Collect on-demand social evidence through WebCMD, with OAuth fallback.

    A provider that returns an empty list is still live. Authentication,
    platform support, and command availability failures remain visible in the
    detail string instead of being converted to a fabricated quiet-crowd zero.
    """
    calls: list[Awaitable[ProviderFetch]] = [
        _reddit_auto(ticker, company, subreddits, timeframe, limit),
        _twitter_webcmd(ticker, company, limit),
    ]

    fetched = await asyncio.gather(*calls, return_exceptions=True)
    live = [item for item in fetched if isinstance(item, ProviderFetch)]
    failures = [item for item in fetched if isinstance(item, BaseException)]
    if not live:
        detail = "; ".join(
            f"{getattr(item, 'source', 'social')}: {getattr(item, 'detail', type(item).__name__)}"
            for item in failures
        ) or "no social provider was available"
        if failures and all(isinstance(item, SourceUnavailable) for item in failures):
            raise SourceUnavailable("social", detail)
        raise SourceError("social", detail)

    merged: dict[str, dict[str, Any]] = {}
    for outcome in live:
        for post in outcome.posts:
            key = f"{post['platform']}:{post['id']}"
            merged[key] = post
    posts = sorted(merged.values(), key=lambda item: item["created_at"])
    live_detail = ", ".join(f"{item.provider} {len(item.posts)}" for item in live)
    failure_detail = "; ".join(
        f"{getattr(item, 'source', 'social')} unavailable: {getattr(item, 'detail', type(item).__name__)}"
        for item in failures
    )
    return SocialFetch(
        posts=posts,
        provider=" + ".join(item.provider for item in live),
        detail="; ".join(part for part in (live_detail, failure_detail) if part),
    )
