from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..markets import base_symbol
from .http import SourceError, request_json

ANNOUNCEMENTS = "https://www.nseindia.com/api/corporate-announcements"

# NSE serves its JSON API only to what looks like a browser session.
_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Announcement subjects that can actually move a narrative, mirroring the
# material-form filter applied to SEC forms.
MATERIAL_KEYWORDS = (
    "financial result",
    "earnings",
    "acquisition",
    "amalgamation",
    "merger",
    "order",
    "contract",
    "award",
    "allotment",
    "fund rais",
    "buyback",
    "dividend",
    "resignation",
    "appointment",
    "credit rating",
    "investor presentation",
    "scheme of arrangement",
    "open offer",
    "preferential issue",
)


def _parse_stamp(raw: str) -> datetime | None:
    """NSE stamps look like '07-Aug-2026 17:07:35' in IST."""
    try:
        naive = datetime.strptime(str(raw).strip(), "%d-%b-%Y %H:%M:%S")
    except (TypeError, ValueError):
        return None
    # IST is UTC+5:30 and NSE publishes local time with no offset.
    return (naive - timedelta(hours=5, minutes=30)).replace(tzinfo=UTC)


def _is_material(subject: str, description: str) -> bool:
    haystack = f"{subject} {description}".lower()
    return any(keyword in haystack for keyword in MATERIAL_KEYWORDS)


async def fetch_announcements(symbol: str, *, lookback_days: int = 90, limit: int = 40) -> list[dict[str, Any]]:
    """Material corporate announcements for an NSE-listed security.

    This is India's counterpart to an SEC filing: an exchange-published,
    timestamped primary source, which is what the catalyst score needs.
    """
    payload = await request_json(
        "nse",
        ANNOUNCEMENTS,
        params={"index": "equities", "symbol": base_symbol(symbol)},
        headers=_HEADERS,
    )
    if not isinstance(payload, list):
        raise SourceError("nse", "announcements response was not a list")

    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    rows: list[dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        at = _parse_stamp(entry.get("an_dt", ""))
        if at is None or at < cutoff:
            continue
        subject = str(entry.get("desc") or entry.get("sm_name") or "").strip()
        description = str(entry.get("attchmntText") or "").strip()
        if not _is_material(subject, description):
            continue
        rows.append(
            {
                "form": subject[:60] or "Announcement",
                "accession": str(entry.get("seq_id") or ""),
                "created_at": at,
                "url": str(entry.get("attchmntFile") or "https://www.nseindia.com/companies-listing/corporate-filings-announcements"),
            }
        )
        if len(rows) >= limit:
            break
    return sorted(rows, key=lambda row: row["created_at"])
