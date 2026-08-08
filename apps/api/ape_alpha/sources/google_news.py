from __future__ import annotations

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus, urlparse
from xml.etree import ElementTree

from ..markets import MarketProfile
from .http import SourceError, request_text
from .naming import company_root

RSS_SEARCH = "https://news.google.com/rss/search"

# Google appends " - Publisher" to every headline. Splitting it off keeps the
# publisher out of the novelty comparison, where it would make two different
# stories from one outlet look more similar than they are.
_TITLE_SUFFIX = re.compile(r"\s+-\s+([^-]+)$")


def _query_for(company: str, symbol: str) -> str:
    root = company_root(company)
    return f'"{root}" stock' if root else f"{symbol} stock"


def _clean_title(raw: str) -> tuple[str, str]:
    match = _TITLE_SUFFIX.search(raw)
    if not match:
        return raw.strip(), ""
    return raw[: match.start()].strip(), match.group(1).strip()


def _parse_date(raw: str) -> datetime | None:
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def fetch_articles(
    symbol: str,
    company: str,
    profile: MarketProfile,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Recent coverage from Google News, in the market's own locale.

    This is the precision leg: it is ticker- and region-scoped, so Indian
    securities return Indian press rather than whatever GDELT's global index
    happened to match. It has no archive, so it never feeds a historical
    baseline — only the current window.
    """
    language, country, ceid = profile.news_locale
    url = (
        f"{RSS_SEARCH}?q={quote_plus(_query_for(company, symbol))}"
        f"&hl={language}&gl={country}&ceid={ceid}"
    )
    body = await request_text(
        "google-news",
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ape-alpha/0.2)", "Accept": "application/rss+xml"},
    )
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise SourceError("google-news", "feed was not parseable XML") from exc

    rows: list[dict[str, Any]] = []
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        created = _parse_date(item.findtext("pubDate") or "")
        if not link or created is None:
            continue
        title, from_title = _clean_title(item.findtext("title") or "")
        if not title:
            continue
        publisher = (item.findtext("source") or from_title or "").strip()
        rows.append(
            {
                "title": title,
                "url": link,
                # Google wraps links in a redirect, so the publisher name is a
                # better identity than the host for credibility scoring.
                "domain": (publisher or urlparse(link).netloc).lower(),
                "language": language,
                "country": country,
                "created_at": created,
            }
        )
        if len(rows) >= limit:
            break
    return sorted(rows, key=lambda row: row["created_at"])
