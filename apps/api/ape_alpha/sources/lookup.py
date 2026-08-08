from __future__ import annotations

from typing import Any

from ..markets import MarketProfile
from .http import SourceError, request_json

YAHOO_SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"

# Yahoo's exchange codes for the venues each market cares about.
EXCHANGES = {
    "US": {"NMS", "NYQ", "NGM", "ASE", "PCX", "BTS", "NCM"},
    "IN": {"NSI", "BSE"},
}

_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; ape-alpha/0.2)",
}


async def search_symbols(query: str, profile: MarketProfile, *, limit: int = 8) -> list[dict[str, Any]]:
    """Resolve free text to listings on this market's venues.

    India has no free equivalent of the SEC's company-ticker file, so Yahoo's
    search index is the resolver there. Results are filtered to the market's own
    exchanges, otherwise a query like "reliance" returns a US steel distributor
    ahead of Reliance Industries.
    """
    payload = await request_json(
        "yahoo-search",
        YAHOO_SEARCH,
        params={"q": query, "quotesCount": str(max(limit, 10)), "newsCount": "0"},
        headers=_HEADERS,
    )
    if not isinstance(payload, dict):
        raise SourceError("yahoo-search", "unexpected response shape")

    allowed = EXCHANGES.get(profile.market.value, set())
    rows: list[dict[str, Any]] = []
    for quote in payload.get("quotes") or []:
        if not isinstance(quote, dict):
            continue
        if quote.get("quoteType") != "EQUITY":
            continue
        symbol = str(quote.get("symbol", "") or "").upper()
        exchange = str(quote.get("exchange", "") or "").upper()
        name = str(quote.get("longname") or quote.get("shortname") or "").strip()
        if not symbol or not name or exchange not in allowed:
            continue
        rows.append(
            {
                "symbol": symbol,
                "exchange": exchange,
                "company": name,
                # Yahoo ranks by relevance; preserve that as the tie-breaker.
                "rank": len(rows),
            }
        )
        if len(rows) >= limit:
            break
    return rows
