from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from .http import SourceError, request_json
from .naming import company_root

DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT indexes worldwide coverage, so a bare company name pulls in unrelated
# press. Pairing the name with market vocabulary keeps the result set on-topic
# without narrowing it to a single outlet.
_MARKET_CONTEXT = "(stock OR shares OR earnings OR investors OR nasdaq OR nyse)"

_GDELT_STAMP = re.compile(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$")

# GDELT's timespan grammar is a number followed by min, h, d, w or m. Anything
# else is not rejected — it is silently ignored and the API falls back to its
# own short default, which looks like "no coverage" rather than a bad request.
_TIMESPAN = re.compile(r"^\d+(min|h|d|w|m)$")


def _parse_stamp(value: str) -> datetime:
    match = _GDELT_STAMP.match(str(value or "").strip())
    if match:
        year, month, day, hour, minute, second = (int(part) for part in match.groups())
        return datetime(year, month, day, hour, minute, second, tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _query_for(company: str, ticker: str) -> str:
    root = company_root(company)
    name = f'"{root}"' if root else ticker
    return f"{name} {_MARKET_CONTEXT}"


def _window_params(
    timespan: str | None,
    start: datetime | None,
    end: datetime | None,
) -> dict[str, str]:
    """GDELT accepts either a relative timespan or an absolute UTC window."""
    if start is not None and end is not None:
        return {
            "startdatetime": start.astimezone(UTC).strftime("%Y%m%d%H%M%S"),
            "enddatetime": end.astimezone(UTC).strftime("%Y%m%d%H%M%S"),
        }
    window = timespan or "7d"
    if not _TIMESPAN.match(window):
        raise SourceError("gdelt", f"timespan {window!r} must look like 24h, 7d, 1w or 3m")
    return {"timespan": window}


async def fetch_articles(
    ticker: str,
    company: str,
    *,
    timespan: str | None = "7d",
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 120,
) -> list[dict[str, Any]]:
    """Point-in-time news coverage for a security.

    GDELT is keyless and supports absolute windows back to 2017, which is what
    makes a genuine historical news backfill possible.
    """
    params: dict[str, str] = {
        "query": _query_for(company, ticker),
        "mode": "artlist",
        "format": "json",
        "sort": "datedesc",
        "maxrecords": str(max(1, min(250, limit))),
    }
    params.update(_window_params(timespan, start, end))

    payload = await request_json("gdelt", DOC_API, params=params, headers={"Accept": "application/json"})
    if not isinstance(payload, dict):
        raise SourceError("gdelt", "unexpected response shape")
    articles = payload.get("articles")
    if articles is None:
        # GDELT answers an empty result set with an object that has no articles
        # key. That is a valid "no coverage" answer, not a failure.
        return []
    if not isinstance(articles, list):
        raise SourceError("gdelt", "articles field was not a list")

    rows: list[dict[str, Any]] = []
    for article in articles:
        url = str(article.get("url", "") or "")
        if not url:
            continue
        rows.append(
            {
                "title": str(article.get("title", "") or "").strip(),
                "url": url,
                "domain": str(article.get("domain", "") or ""),
                "language": str(article.get("language", "") or ""),
                "country": str(article.get("sourcecountry", "") or ""),
                "created_at": _parse_stamp(article.get("seendate", "")),
            }
        )
    return sorted(rows, key=lambda item: item["created_at"])


async def fetch_volume_timeline(
    ticker: str,
    company: str,
    *,
    timespan: str | None = "3m",
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[tuple[datetime, float]]:
    """Daily coverage-intensity series.

    This is the baseline the news z-score is measured against. Without it, a
    story's news volume has nothing to be abnormal relative to. Absolute windows
    reach back to 2017, which is what makes the historical backfill real.
    """
    params: dict[str, str] = {
        "query": _query_for(company, ticker),
        "mode": "timelinevol",
        "format": "json",
    }
    params.update(_window_params(timespan, start, end))
    payload = await request_json("gdelt", DOC_API, params=params, headers={"Accept": "application/json"})
    if not isinstance(payload, dict):
        raise SourceError("gdelt", "unexpected timeline response shape")
    timeline = payload.get("timeline") or []
    if not timeline:
        return []
    series = timeline[0].get("data") or []
    points: list[tuple[datetime, float]] = []
    for point in series:
        try:
            points.append((_parse_stamp(point.get("date", "")), float(point.get("value", 0.0))))
        except (ValueError, TypeError):
            continue
    return points
