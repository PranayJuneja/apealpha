from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from ape_alpha.sources import market, news, reddit
from ape_alpha.sources.http import SourceError, cache
from ape_alpha.sources.naming import company_root


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    cache().clear()


@pytest.mark.parametrize(
    ("registered", "expected"),
    [
        ("Rocket Lab USA, Inc.", "Rocket Lab"),
        ("AST SpaceMobile, Inc.", "AST SpaceMobile"),
        ("Apple Inc.", "Apple"),
        ("The Trade Desk, Inc.", "Trade Desk"),
        ("GameStop Corp.", "GameStop"),
        ("Advanced Micro Devices, Inc.", "Advanced Micro Devices"),
        ("Holdings Group Ltd", ""),
    ],
)
def test_company_root_strips_legal_and_geographic_noise(registered: str, expected: str) -> None:
    assert company_root(registered) == expected


def test_gdelt_stamps_parse_into_utc() -> None:
    assert news._parse_stamp("20260808T143000Z") == datetime(2026, 8, 8, 14, 30, tzinfo=UTC)


def test_gdelt_query_pairs_the_company_with_market_context() -> None:
    query = news._query_for("Apple Inc.", "AAPL")
    assert '"Apple"' in query
    assert "stock" in query


def test_gdelt_query_falls_back_to_the_symbol_for_short_names() -> None:
    assert news._query_for("BP", "BP").startswith("BP ")


def test_absolute_window_beats_relative_timespan() -> None:
    window = news._window_params(
        "7d", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 2, 1, tzinfo=UTC)
    )
    assert window == {"startdatetime": "20240101000000", "enddatetime": "20240201000000"}
    assert news._window_params("7d", None, None) == {"timespan": "7d"}


@pytest.mark.parametrize("window", ["15min", "24h", "7d", "1w", "3m"])
def test_valid_gdelt_timespans_pass_through(window: str) -> None:
    assert news._window_params(window, None, None) == {"timespan": window}


@pytest.mark.parametrize("window", ["3months", "1week", "90days", "3M", "abc", "3"])
def test_invalid_gdelt_timespans_are_rejected_not_silently_ignored(window: str) -> None:
    # GDELT answers an unparseable unit with its own short default window, which
    # reads downstream as "this company has no coverage".
    with pytest.raises(SourceError):
        news._window_params(window, None, None)


@pytest.mark.asyncio
async def test_empty_gdelt_result_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_request(*_: Any, **__: Any) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(news, "request_json", fake_request)
    assert await news.fetch_articles("AAPL", "Apple Inc.") == []


@pytest.mark.asyncio
async def test_malformed_gdelt_articles_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_request(*_: Any, **__: Any) -> dict[str, Any]:
        return {"articles": "not a list"}

    monkeypatch.setattr(news, "request_json", fake_request)
    with pytest.raises(SourceError):
        await news.fetch_articles("AAPL", "Apple Inc.")


def test_reddit_requires_a_whole_token_match() -> None:
    post = {"title": "Thoughts on ASTS today", "selftext": ""}
    assert reddit._mentions_ticker(post, "ASTS", "AST SpaceMobile") is True

    substring = {"title": "PASTSAUCE is trending", "selftext": ""}
    assert reddit._mentions_ticker(substring, "ASTS", "AST SpaceMobile") is False


def test_reddit_accepts_a_company_name_match() -> None:
    post = {"title": "Rocket Lab keeps winning launches", "selftext": ""}
    assert reddit._mentions_ticker(post, "RKLB", "Rocket Lab USA, Inc.") is True


def test_reddit_ignores_short_company_roots() -> None:
    post = {"title": "bp is fine", "selftext": ""}
    assert reddit._mentions_ticker(post, "BP", "BP") is False


def test_reddit_normalizes_into_stable_fields() -> None:
    normalized = reddit._normalize(
        {
            "id": "abc",
            "title": " Big DD ",
            "selftext": "body text",
            "author": "someone",
            "subreddit": "stocks",
            "link_flair_text": "DD",
            "score": 42,
            "num_comments": 7,
            "upvote_ratio": 0.93,
            "created_utc": 1_780_000_000,
            "permalink": "/r/stocks/comments/abc/",
        },
        "ASTS",
    )
    assert normalized["title"] == "Big DD"
    assert normalized["body_length"] == len("body text")
    assert normalized["url"].startswith("https://www.reddit.com/r/stocks")
    assert normalized["created_at"].tzinfo is not None


@pytest.mark.asyncio
async def test_live_alpaca_request_uses_intraday_resolution_and_includes_today(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class Config:
        alpaca_enabled = True

    async def fake_alpaca(
        ticker: str, *, start: Any, end: Any, timeframe: str
    ) -> list[market.Bar]:
        captured.update(ticker=ticker, start=start, end=end, timeframe=timeframe)
        return [market.Bar(datetime.now(UTC), 1, 1, 1, 1, 1)]

    monkeypatch.setattr(market, "settings", lambda: Config())
    monkeypatch.setattr(market, "_alpaca_bars", fake_alpaca)

    _, provider = await market.fetch_bars("AAPL", lookback_days=7, timeframe="1Hour")
    assert provider == "alpaca"
    assert captured["timeframe"] == "1Hour"
    assert captured["end"] == datetime.now(UTC).date() + timedelta(days=1)
