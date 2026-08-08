from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from ape_alpha.backtest import benchmark_for
from ape_alpha.markets import INDIA, US, Market, base_symbol, profile
from ape_alpha.research.engine import merge_articles
from ape_alpha.sources import google_news, nse
from ape_alpha.sources.lookup import EXCHANGES


def test_each_market_is_measured_against_its_own_index() -> None:
    # Scoring an Indian security against the S&P would book Nifty moves and the
    # currency basis as strategy performance.
    assert benchmark_for("US") == "SPY"
    assert benchmark_for("IN") == "^NSEI"
    assert benchmark_for(None) == "SPY"
    assert benchmark_for("nonsense") == "SPY"


def test_market_profiles_are_distinct_where_it_matters() -> None:
    assert US.currency != INDIA.currency
    assert US.benchmark != INDIA.benchmark
    assert US.filing_source != INDIA.filing_source
    assert not set(US.subreddits) & set(INDIA.subreddits)
    assert US.news_locale[1] == "US" and INDIA.news_locale[1] == "IN"


def test_venue_suffixes_are_stripped_for_display() -> None:
    assert base_symbol("RELIANCE.NS") == "RELIANCE"
    assert base_symbol("RELIANCE.BO") == "RELIANCE"
    assert base_symbol("AAPL") == "AAPL"


def test_symbol_search_only_accepts_the_market_s_own_venues() -> None:
    assert "NSI" in EXCHANGES["IN"] and "BSE" in EXCHANGES["IN"]
    assert "NMS" in EXCHANGES["US"]
    # A US venue must never satisfy an India query, or "reliance" returns a US
    # steel distributor ahead of Reliance Industries.
    assert not EXCHANGES["IN"] & EXCHANGES["US"]


def test_profile_lookup_accepts_enum_or_string() -> None:
    assert profile("IN") is INDIA
    assert profile(Market.US) is US


def test_google_news_strips_the_publisher_suffix_from_headlines() -> None:
    title, publisher = google_news._clean_title("Reliance beats Q1 estimates - The Economic Times")
    assert title == "Reliance beats Q1 estimates"
    assert publisher == "The Economic Times"
    plain, empty = google_news._clean_title("No publisher here")
    assert plain == "No publisher here" and empty == ""


def test_nse_stamps_convert_from_ist_to_utc() -> None:
    # 17:07 IST is 11:37 UTC; treating it as UTC would move the event 5.5 hours
    # earlier and corrupt every "who knew first" ordering.
    assert nse._parse_stamp("07-Aug-2026 17:07:35") == datetime(2026, 8, 7, 11, 37, 35, tzinfo=UTC)
    assert nse._parse_stamp("garbage") is None


def test_nse_keeps_only_material_announcements() -> None:
    assert nse._is_material("Acquisition of subsidiary", "") is True
    assert nse._is_material("Financial Results", "") is True
    assert nse._is_material("Trading window closure reminder", "") is False


def article(title: str, day: int, domain: str = "x.com") -> dict[str, Any]:
    return {
        "title": title,
        "url": f"https://{domain}/{title}",
        "domain": domain,
        "language": "en",
        "country": "US",
        "created_at": datetime(2026, 8, day, 12, 0, tzinfo=UTC),
    }


def test_merging_news_providers_counts_a_shared_story_once() -> None:
    gdelt = [article("Acme wins contract", 5), article("Acme names new CFO", 6)]
    google = [article("Acme wins contract", 5, "other.com"), article("Acme opens plant", 7)]
    merged = merge_articles(gdelt, google)
    titles = [row["title"] for row in merged]
    assert titles.count("Acme wins contract") == 1
    assert len(merged) == 3


def test_the_same_headline_on_a_different_day_is_a_different_story() -> None:
    merged = merge_articles([article("Quarterly update", 5)], [article("Quarterly update", 6)])
    assert len(merged) == 2


def test_merging_survives_an_empty_or_failed_provider() -> None:
    assert merge_articles([], []) == []
    assert len(merge_articles([article("Solo", 5)], [])) == 1


@pytest.mark.parametrize("market", ["US", "IN"])
def test_every_market_has_a_reachable_filing_leg(market: str) -> None:
    assert profile(market).filing_source in {"sec", "nse"}
    assert profile(market).filing_label
