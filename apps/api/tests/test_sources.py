from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from ape_alpha.markets import US
from ape_alpha.sources import live_news, market, news, reddit, social
from ape_alpha.sources.http import SourceError, SourceUnavailable, cache
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


def test_social_search_recognizes_an_explicit_ticker() -> None:
    assert social._explicit_ticker("Why I still own $PLTR", "PLTR") is True


def test_twitter_normalizes_into_the_shared_social_shape() -> None:
    normalized = social._normalize_twitter(
        {
            "id": "123",
            "author": "alice",
            "text": "$PLTR demand looks strong",
            "created_at": "Sat Aug 08 10:00:00 +0000 2026",
            "likes": 12,
            "views": "450",
            "url": "https://x.com/alice/status/123",
            "has_media": True,
        },
        "PLTR",
    )
    assert normalized["platform"] == "x"
    assert normalized["author"] == "@alice"
    assert normalized["score"] == 12
    assert normalized["views"] == 450
    assert normalized["created_at"].tzinfo is not None


@pytest.mark.asyncio
async def test_webcmd_reddit_query_is_one_argument_and_filters_false_positives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: tuple[str, ...] = ()

    class Config:
        webcmd_timeout_seconds = 12.0

    async def fake_invoke(args: tuple[str, ...], **_: Any) -> list[dict[str, Any]]:
        nonlocal captured
        captured = args
        return [
            {
                "id": "good",
                "title": "PLTR valuation discussion",
                "subreddit": "r/PLTR",
                "author": "alice",
                "created_utc": 1_780_000_000,
                "url": "https://reddit.com/good",
            },
            {
                "id": "noise",
                "title": "Palantir fantasy character",
                "subreddit": "r/fantasy",
                "author": "bob",
                "created_utc": 1_780_000_000,
                "url": "https://reddit.com/noise",
            },
        ]

    monkeypatch.setattr(social, "settings", lambda: Config())
    monkeypatch.setattr(social, "invoke_json", fake_invoke)
    result = await social._reddit_webcmd("PLTR", "Palantir Technologies Inc.", ("stocks",), "week", 10)
    assert captured[2] == '$PLTR OR PLTR OR "Palantir"'
    assert [post["id"] for post in result.posts] == ["good"]


@pytest.mark.asyncio
async def test_auto_mode_falls_back_to_reddit_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    class Config:
        social_mode = "auto"
        reddit_enabled = True

    async def unavailable(*_: Any, **__: Any) -> social.ProviderFetch:
        raise SourceUnavailable("webcmd-reddit", "login required")

    async def oauth(*_: Any, **__: Any) -> social.ProviderFetch:
        return social.ProviderFetch("reddit-oauth", [])

    monkeypatch.setattr(social, "settings", lambda: Config())
    monkeypatch.setattr(social, "_reddit_webcmd", unavailable)
    monkeypatch.setattr(social, "_reddit_oauth", oauth)
    result = await social._reddit_auto("PLTR", "Palantir", ("stocks",), "week", 10)
    assert result.provider == "reddit-oauth"


@pytest.mark.asyncio
async def test_empty_reddit_search_is_still_live_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Config:
        social_mode = "webcmd"

    async def reddit_live(*_: Any, **__: Any) -> social.ProviderFetch:
        return social.ProviderFetch("webcmd-reddit", [])

    async def twitter_unavailable(*_: Any, **__: Any) -> social.ProviderFetch:
        raise SourceUnavailable("webcmd-twitter", "login required")

    monkeypatch.setattr(social, "settings", lambda: Config())
    monkeypatch.setattr(social, "_reddit_auto", reddit_live)
    monkeypatch.setattr(social, "_twitter_webcmd", twitter_unavailable)
    result = await social.fetch_mentions("PLTR", "Palantir", subreddits=("stocks",), limit=10)
    assert result.provider == "webcmd-reddit"
    assert "webcmd-reddit 0" in result.detail
    assert "webcmd-twitter unavailable" in result.detail


@pytest.mark.asyncio
async def test_social_fetch_merges_reddit_and_x(monkeypatch: pytest.MonkeyPatch) -> None:
    stamp = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)

    async def reddit_live(*_: Any, **__: Any) -> social.ProviderFetch:
        return social.ProviderFetch("webcmd-reddit", [{
            "id": "r1", "platform": "reddit", "created_at": stamp,
        }])

    async def twitter_live(*_: Any, **__: Any) -> social.ProviderFetch:
        return social.ProviderFetch("webcmd-twitter", [{
            "id": "x1", "platform": "x", "created_at": stamp + timedelta(minutes=1),
        }])

    monkeypatch.setattr(social, "_reddit_auto", reddit_live)
    monkeypatch.setattr(social, "_twitter_webcmd", twitter_live)
    result = await social.fetch_mentions("PLTR", "Palantir", subreddits=("stocks",), limit=10)
    assert [post["id"] for post in result.posts] == ["r1", "x1"]
    assert result.provider == "webcmd-reddit + webcmd-twitter"


@pytest.mark.asyncio
async def test_webcmd_news_runs_google_and_yahoo_for_each_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    class Config:
        webcmd_timeout_seconds = 12.0

    async def fake_invoke(args: tuple[str, ...], **_: Any) -> list[dict[str, Any]]:
        calls.append(args)
        provider = "google-news" if args[1] == "google-news" else "yahoo-news"
        return [{
            "title": f"Palantir story from {provider}",
            "url": f"https://example.com/{provider}",
            "publisher": "Example",
            "createdAt": "2026-08-08T10:00:00Z",
            "language": "en-US",
            "country": "US",
            "provider": provider,
        }]

    monkeypatch.setattr(live_news, "settings", lambda: Config())
    monkeypatch.setattr(live_news, "invoke_json", fake_invoke)
    result = await live_news.fetch_articles("PLTR", "Palantir Technologies Inc.", US)
    assert {call[1] for call in calls} == {"google-news", "yahoo-news"}
    assert result.provider == "webcmd-google-news + webcmd-yahoo-news"
    assert {article["provider"] for article in result.articles} == {"google-news", "yahoo-news"}


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
