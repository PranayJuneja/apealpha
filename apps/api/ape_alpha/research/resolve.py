from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from ..markets import Market, MarketProfile, base_symbol, profile as market_profile
from ..sources.lookup import search_symbols
from ..sources.sec import load_universe

# Symbols that collide with ordinary English. A bare match on these is never
# enough; the query has to cashtag them or name the company.
AMBIGUOUS_WORDS = {
    "A", "ALL", "AN", "ANY", "ARE", "AT", "BE", "BIG", "BY", "CAN", "DD", "DO",
    "EAT", "FOR", "GO", "GOOD", "HAS", "HE", "IT", "LOW", "NEW", "NOW", "ON",
    "ONE", "OR", "OUT", "PLAY", "REAL", "SO", "T", "TRUE", "TWO", "UK", "USA",
    "WE", "Y",
}

# Symbol changes that matter for point-in-time correctness: scoring a 2021 event
# under today's symbol would quietly rewrite history.
ALIASES: dict[str, list[tuple[date, date, str]]] = {
    "FB": [(date.min, date(2022, 6, 8), "FB"), (date(2022, 6, 9), date.max, "META")],
    "META": [(date.min, date(2022, 6, 8), "FB"), (date(2022, 6, 9), date.max, "META")],
    "TWTR": [(date.min, date(2022, 10, 27), "TWTR")],
    "SQ": [(date.min, date(2023, 12, 1), "SQ"), (date(2023, 12, 2), date.max, "XYZ")],
    "FISV": [(date.min, date(2024, 2, 6), "FISV"), (date(2024, 2, 7), date.max, "FI")],
}

_STOPWORDS = {"inc", "corp", "corporation", "co", "company", "ltd", "limited", "plc", "holdings", "group", "the"}


@dataclass(frozen=True)
class Resolution:
    """A resolved listing.

    `ticker` is the venue-qualified symbol used for data access (RELIANCE.NS);
    `display_symbol` is what a human calls it (RELIANCE). `cik` is 0 outside the
    United States, where there is no such identifier.
    """

    ticker: str
    display_symbol: str
    company: str
    cik: int
    market: Market
    confidence: float
    matched_on: str

    @property
    def profile(self) -> MarketProfile:
        return market_profile(self.market)


def _normalize_name(value: str) -> list[str]:
    tokens = re.split(r"[^a-z0-9]+", value.lower())
    return [token for token in tokens if token and token not in _STOPWORDS]


def apply_alias(symbol: str, as_of: date) -> str:
    """The symbol this security actually traded under on a given date."""
    for start, end, mapped in ALIASES.get(symbol.upper(), []):
        if start <= as_of <= end:
            return mapped
    return symbol.upper()


async def _resolve_us(query: str, as_of: date, limit: int) -> list[Resolution]:
    raw = query.strip()
    universe = await load_universe()
    cashtagged = raw.startswith("$")
    symbol = raw.lstrip("$").upper().strip()
    matches: list[Resolution] = []

    # Exact symbol. An ambiguous word only counts when explicitly cashtagged.
    if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", symbol) and symbol in universe:
        if symbol not in AMBIGUOUS_WORDS or cashtagged:
            entry = universe[symbol]
            aliased = apply_alias(symbol, as_of)
            matches.append(
                Resolution(
                    ticker=aliased,
                    display_symbol=aliased,
                    company=entry["company"],
                    cik=entry["cik"],
                    market=Market.US,
                    confidence=0.99 if cashtagged else 0.94,
                    matched_on="symbol",
                )
            )

    tokens = _normalize_name(raw)
    if tokens:
        seen = {match.ticker for match in matches}
        scored: list[tuple[float, Resolution]] = []
        for entry in universe.values():
            if entry["ticker"] in seen:
                continue
            name_tokens = _normalize_name(entry["company"])
            if not name_tokens:
                continue
            overlap = len(set(tokens) & set(name_tokens))
            if not overlap:
                continue
            coverage = overlap / len(tokens)
            precision = overlap / len(name_tokens)
            score = coverage * 0.7 + precision * 0.3
            if " ".join(tokens) == " ".join(name_tokens):
                score = 1.0
            if score < 0.34:
                continue
            aliased = apply_alias(entry["ticker"], as_of)
            scored.append(
                (
                    score,
                    Resolution(
                        ticker=aliased,
                        display_symbol=aliased,
                        company=entry["company"],
                        cik=entry["cik"],
                        market=Market.US,
                        confidence=round(min(0.93, 0.45 + score * 0.5), 3),
                        matched_on="company_name",
                    ),
                )
            )
        scored.sort(key=lambda item: (-item[0], len(item[1].company)))
        matches.extend(resolution for _, resolution in scored[:limit])

    return matches[:limit]


async def _resolve_india(query: str, limit: int) -> list[Resolution]:
    """India has no free authoritative ticker file, so the venue index is used.

    Yahoo's search covers both NSE and BSE. NSE is preferred when a security is
    dual-listed, because it carries the large majority of Indian equity volume
    and is the venue whose announcements feed the filings leg.
    """
    raw = query.strip().lstrip("$")
    rows = await search_symbols(raw, market_profile(Market.IN), limit=limit * 2)

    resolutions: list[Resolution] = []
    for row in rows:
        exact = base_symbol(row["symbol"]).upper() == raw.upper()
        nse = row["exchange"] == "NSI"
        confidence = 0.95 if exact and nse else 0.9 if exact else 0.82 if nse else 0.7
        resolutions.append(
            Resolution(
                ticker=row["symbol"],
                display_symbol=base_symbol(row["symbol"]),
                company=row["company"],
                cik=0,
                market=Market.IN,
                confidence=confidence,
                matched_on="symbol" if exact else "company_name",
            )
        )

    # Collapse dual listings to one entry per company, keeping the NSE line.
    best: dict[str, Resolution] = {}
    for item in resolutions:
        current = best.get(item.display_symbol)
        if current is None or item.confidence > current.confidence:
            best[item.display_symbol] = item
    ordered = sorted(best.values(), key=lambda item: -item.confidence)
    return ordered[:limit]


async def resolve(
    query: str,
    *,
    market: Market | str = Market.US,
    as_of: date | None = None,
    limit: int = 5,
) -> list[Resolution]:
    """Turn free text into ranked listing candidates for one market.

    Accepts a cashtag, a bare symbol or a company name, because that is what
    people actually type. Returns candidates rather than a single answer so an
    ambiguous query can be disambiguated in the UI instead of guessed at.
    """
    if not query.strip():
        return []
    if Market(market) is Market.IN:
        return await _resolve_india(query, limit)
    return await _resolve_us(query, as_of or date.today(), limit)
