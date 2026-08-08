from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ape_alpha.research.features import (
    build_features,
    catalyst_quality,
    dd_density,
    market_features,
    novelty,
    sentiment_ratio,
)
from ape_alpha.sources.market import Bar

NOW = datetime(2026, 8, 8, 15, 0, tzinfo=UTC)


def post(hours_ago: float, *, author: str, title: str = "", body: str = "", flair: str = "") -> dict:
    return {
        "id": f"{author}{hours_ago}",
        "ticker": "TEST",
        "title": title,
        "body": body,
        "author": author,
        "subreddit": "stocks",
        "flair": flair,
        "score": 10,
        "comments": 4,
        "upvote_ratio": 0.8,
        "body_length": len(body),
        "created_at": NOW - timedelta(hours=hours_ago),
        "url": "https://reddit.com/x",
    }


def bars(closes: list[float], volumes: list[float] | None = None) -> list[Bar]:
    volumes = volumes or [1_000_000.0] * len(closes)
    return [
        Bar(
            at=NOW - timedelta(days=len(closes) - index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=volumes[index],
        )
        for index, close in enumerate(closes)
    ]


def test_sentiment_is_neutral_without_directional_language() -> None:
    assert sentiment_ratio(["the company filed a document today"]) == 0.5
    assert sentiment_ratio(["bullish breakout, buying calls"]) > 0.8
    assert sentiment_ratio(["bearish, dilution risk, puts"]) < 0.2


def test_dd_density_counts_argument_not_volume() -> None:
    assert dd_density([post(1, author="a", body="x" * 900)]) == 1.0
    assert dd_density([post(1, author="a", body="short")]) == 0.0
    assert dd_density([post(1, author="a", flair="DD")]) == 1.0
    assert dd_density([]) == 0.0


def test_novelty_discounts_syndicated_repetition() -> None:
    original = ["Acme wins major defense contract"]
    assert novelty(["Acme wins major defense contract"], original) < 0.5
    assert novelty(["Acme chief financial officer resigns unexpectedly"], original) == 1.0


def test_catalyst_quality_rewards_primary_evidence() -> None:
    filing = [{"form": "8-K", "created_at": NOW - timedelta(hours=5), "url": "x", "accession": "y"}]
    with_filing = catalyst_quality(filing, [{"domain": "reuters.com"}], NOW)
    without = catalyst_quality([], [{"domain": "someblog.example"}], NOW)
    assert with_filing > without
    assert 0.0 <= with_filing <= 1.0


def test_stale_filings_do_not_count_as_catalysts() -> None:
    stale = [{"form": "8-K", "created_at": NOW - timedelta(days=30), "url": "x", "accession": "y"}]
    assert catalyst_quality(stale, [], NOW) == 0.0


def test_market_features_refuse_to_score_thin_history() -> None:
    assert market_features(bars([10.0, 10.5, 11.0])) == {
        "market_z": 0.0,
        "relative_volume": 1.0,
        "abnormal_return_recent": 0.0,
        "pre_signal_return": 0.0,
    }


def test_market_features_detect_an_abnormal_move() -> None:
    flat = [100.0 + (index % 2) * 0.1 for index in range(60)]
    computed = market_features(bars(flat + [130.0]))
    assert computed["market_z"] > 3
    assert computed["abnormal_return_recent"] > 0.25


def test_relative_volume_uses_the_prior_median() -> None:
    closes = [100.0] * 30
    volumes = [1_000_000.0] * 29 + [5_000_000.0]
    assert market_features(bars(closes, volumes))["relative_volume"] == 5.0


def test_build_features_produces_a_real_gap_from_real_inputs() -> None:
    posts = [post(hours, author=f"u{hours}", title="bullish breakout", body="x" * 900) for hours in range(0, 20, 2)]
    posts += [post(hours, author=f"o{hours}", title="quiet") for hours in range(30, 160, 24)]
    timeline = [(NOW - timedelta(days=day), 0.01) for day in range(20, 0, -1)]

    computed = build_features(
        posts=posts,
        articles=[],
        news_timeline=timeline,
        bars=bars([100.0 + index * 0.01 for index in range(60)]),
        filings=[],
        as_of=NOW,
    )
    assert computed.social_count == 10
    assert computed.unique_authors == 10
    assert computed.social_z > 0
    assert computed.dd_density == 1.0
    assert computed.bull_ratio > 0.5
    assert computed.social_news_gap == round(computed.social_z - computed.news_z, 4)


def test_build_features_stays_neutral_when_every_leg_is_empty() -> None:
    computed = build_features(posts=[], articles=[], news_timeline=[], bars=[], filings=[], as_of=NOW)
    assert computed.social_count == 0
    assert computed.social_z == 0.0
    assert computed.news_z == 0.0
    assert computed.market_z == 0.0
    assert computed.already_pumped_penalty == 0.0
