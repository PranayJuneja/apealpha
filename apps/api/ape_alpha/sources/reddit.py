from __future__ import annotations

import asyncio
import re
import time
from datetime import UTC, datetime
from typing import Any

from ..config import settings
from .http import SourceError, SourceUnavailable, request_json
from .naming import company_root

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE = "https://oauth.reddit.com"

# Retail equity discussion concentrates in a small number of places. Searching a
# multireddit keeps this to one request per query term instead of one per sub.
SUBREDDITS = (
    "wallstreetbets",
    "stocks",
    "investing",
    "StockMarket",
    "options",
    "pennystocks",
    "smallstreetbets",
    "SecurityAnalysis",
    "ValueInvesting",
)

# Reddit's documented free-tier ceiling is 100 requests per minute per client.
# Four concurrent requests keeps a single research run well inside it.
_CONCURRENCY = asyncio.Semaphore(4)

_token: tuple[str, float] | None = None
_token_lock = asyncio.Lock()


async def _access_token() -> str:
    """App-only OAuth token, refreshed a minute before it expires."""
    global _token
    config = settings()
    if not config.reddit_enabled:
        raise SourceUnavailable("reddit", "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are not set")
    async with _token_lock:
        if _token is not None and _token[1] > time.monotonic():
            return _token[0]
        payload = await request_json(
            "reddit",
            TOKEN_URL,
            method="POST",
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": config.reddit_user_agent},
            auth=(config.reddit_client_id, config.reddit_client_secret),
            use_cache=False,
        )
        token = payload.get("access_token")
        if not token:
            raise SourceError("reddit", "access token missing from OAuth response")
        expires_in = float(payload.get("expires_in", 3600))
        _token = (token, time.monotonic() + max(60.0, expires_in - 60.0))
        return token


def reset_token_cache() -> None:
    """Drop the cached OAuth token. Used by tests and credential rotation."""
    global _token
    _token = None


async def _search(
    query: str, *, timeframe: str, limit: int, subreddits: tuple[str, ...]
) -> list[dict[str, Any]]:
    token = await _access_token()
    config = settings()
    async with _CONCURRENCY:
        payload = await request_json(
            "reddit",
            f"{API_BASE}/r/{'+'.join(subreddits)}/search",
            params={
                "q": query,
                "restrict_sr": "1",
                "sort": "new",
                "t": timeframe,
                "type": "link",
                "limit": str(limit),
                "raw_json": "1",
            },
            headers={"Authorization": f"Bearer {token}", "User-Agent": config.reddit_user_agent},
        )
    children = payload.get("data", {}).get("children", [])
    return [child.get("data", {}) for child in children if isinstance(child, dict)]


def _mentions_ticker(post: dict[str, Any], ticker: str, company: str) -> bool:
    """Require an explicit symbol or a company-name match.

    Reddit's search is loose, so a returned post is treated as a mention only if
    the symbol appears as a whole token (optionally cashtagged) or the company
    name appears in the text. This is what keeps 'IT' or 'ALL' from turning every
    post into a signal.
    """
    haystack = f"{post.get('title', '')} {post.get('selftext', '')}"
    if re.search(rf"(?<![A-Za-z0-9]){re.escape(ticker)}(?![A-Za-z0-9])", haystack):
        return True
    root = company_root(company)
    return bool(root) and root.lower() in haystack.lower()


def _normalize(post: dict[str, Any], ticker: str) -> dict[str, Any]:
    created = datetime.fromtimestamp(float(post.get("created_utc", 0)), tz=UTC)
    permalink = post.get("permalink", "")
    body = str(post.get("selftext", "") or "")
    return {
        "id": str(post.get("id", "")),
        "ticker": ticker,
        "title": str(post.get("title", "") or "").strip(),
        "body": body,
        "author": str(post.get("author", "") or "[deleted]"),
        "subreddit": str(post.get("subreddit", "") or ""),
        "flair": str(post.get("link_flair_text", "") or ""),
        "score": int(post.get("score", 0) or 0),
        "comments": int(post.get("num_comments", 0) or 0),
        "upvote_ratio": float(post.get("upvote_ratio", 0.5) or 0.5),
        "body_length": len(body),
        "created_at": created,
        "url": f"https://www.reddit.com{permalink}" if permalink else str(post.get("url", "")),
    }


async def fetch_mentions(
    ticker: str,
    company: str,
    *,
    subreddits: tuple[str, ...] = SUBREDDITS,
    timeframe: str = "week",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Every post in the window that genuinely mentions this security.

    Searches the cashtag, the bare symbol and the company name, then merges on
    post id. Raises SourceUnavailable when Reddit credentials are absent so the
    caller can mark the social leg as dark rather than silently scoring zero.
    """
    # Checked before dispatch: "not configured" and "the request failed" are
    # different states, and gather() would flatten them into one generic error.
    # Downstream, only "unavailable" blocks a position from being sized.
    if not settings().reddit_enabled:
        raise SourceUnavailable("reddit", "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are not set")

    root = company_root(company)
    queries = [f"${ticker}", ticker]
    if root:
        queries.append(f'"{root}"')

    results = await asyncio.gather(
        *(
            _search(query, timeframe=timeframe, limit=limit, subreddits=subreddits)
            for query in queries
        ),
        return_exceptions=True,
    )

    merged: dict[str, dict[str, Any]] = {}
    failures: list[BaseException] = []
    for result in results:
        if isinstance(result, BaseException):
            failures.append(result)
            continue
        for post in result:
            if not _mentions_ticker(post, ticker, company):
                continue
            normalized = _normalize(post, ticker)
            if normalized["id"]:
                merged[normalized["id"]] = normalized

    if len(failures) == len(queries):
        # Preserve an authentication failure as "unavailable"; a token that is
        # rejected leaves the leg just as dark as one that was never configured.
        if any(isinstance(failure, SourceUnavailable) for failure in failures):
            raise SourceUnavailable("reddit", "Reddit credentials were rejected")
        raise SourceError("reddit", "every search query failed")
    return sorted(merged.values(), key=lambda item: item["created_at"])
