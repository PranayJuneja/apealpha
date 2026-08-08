from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..config import settings
from .http import SourceError, request_json

COMPANY_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"

# Forms that can move a narrative from rumour to fact. Everything else is
# routine and would only add noise to the catalyst score.
MATERIAL_FORMS = {"8-K", "6-K", "S-1", "S-3", "424B4", "13D", "SC 13D", "SC 13G", "10-Q", "10-K"}

_universe: dict[str, dict[str, Any]] | None = None


def _headers() -> dict[str, str]:
    return {"User-Agent": settings().sec_user_agent, "Accept": "application/json"}


async def load_universe() -> dict[str, dict[str, Any]]:
    """Every SEC-registered US listing, keyed by ticker.

    This doubles as the ticker universe and the company-name index, which is
    what lets a free-text query resolve without a paid reference-data feed.
    """
    global _universe
    if _universe is not None:
        return _universe

    payload = await request_json("sec", COMPANY_TICKERS, headers=_headers())
    if not isinstance(payload, dict):
        raise SourceError("sec", "company ticker file had an unexpected shape")

    universe: dict[str, dict[str, Any]] = {}
    for entry in payload.values():
        if not isinstance(entry, dict):
            continue
        ticker = str(entry.get("ticker", "") or "").upper().strip()
        title = str(entry.get("title", "") or "").strip()
        cik = entry.get("cik_str")
        if not ticker or not title or cik is None:
            continue
        universe[ticker] = {"ticker": ticker, "company": title, "cik": int(cik)}
    if not universe:
        raise SourceError("sec", "company ticker file was empty")
    _universe = universe
    return universe


def reset_universe_cache() -> None:
    """Drop the cached listing universe."""
    global _universe
    _universe = None


async def fetch_filings(cik: int, *, lookback_days: int = 90, limit: int = 40) -> list[dict[str, Any]]:
    """Recent material filings for a CIK, newest first.

    The SEC publishes acceptance timestamps, which is the only defensible
    "first knowable" moment for a filing — the filing date alone would let a
    signal look ahead by up to a day.
    """
    payload = await request_json("sec", SUBMISSIONS.format(cik=cik), headers=_headers())
    recent = ((payload or {}).get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    if not forms:
        return []

    accession = recent.get("accessionNumber") or []
    filing_dates = recent.get("filingDate") or []
    acceptance = recent.get("acceptanceDateTime") or []
    documents = recent.get("primaryDocument") or []
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

    rows: list[dict[str, Any]] = []
    for index, form in enumerate(forms):
        if form not in MATERIAL_FORMS:
            continue
        raw_stamp = acceptance[index] if index < len(acceptance) else ""
        try:
            if raw_stamp:
                at = datetime.fromisoformat(str(raw_stamp).replace("Z", "+00:00"))
                at = at if at.tzinfo else at.replace(tzinfo=UTC)
            else:
                day = datetime.fromisoformat(str(filing_dates[index]))
                at = day.replace(tzinfo=UTC)
        except (ValueError, IndexError):
            continue
        if at < cutoff:
            continue

        number = str(accession[index]) if index < len(accession) else ""
        document = str(documents[index]) if index < len(documents) else ""
        stripped = number.replace("-", "")
        rows.append(
            {
                "form": str(form),
                "accession": number,
                "created_at": at,
                "url": (
                    f"https://www.sec.gov/Archives/edgar/data/{cik}/{stripped}/{document}"
                    if stripped and document
                    else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik:010d}"
                ),
            }
        )
        if len(rows) >= limit:
            break
    return sorted(rows, key=lambda item: item["created_at"])
