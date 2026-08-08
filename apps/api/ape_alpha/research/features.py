from __future__ import annotations

import re
import statistics
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable, Sequence

from ..contracts import SignalFeatures
from ..signals import already_pumped_penalty, robust_zscore
from ..sources.market import Bar

# Sentiment is scored with a transparent lexicon rather than a model, because the
# ratio feeds a trading rule and has to be explainable when it is wrong.
_BULL_TERMS = {
    "buy": 1.0, "long": 1.0, "calls": 1.2, "moon": 1.1, "squeeze": 1.0, "bullish": 1.5,
    "undervalued": 1.4, "breakout": 1.2, "rally": 1.0, "upside": 1.2, "beat": 1.0,
    "accumulate": 1.2, "oversold": 0.8, "catalyst": 0.7, "yolo": 0.9, "bagholder": -0.4,
}
_BEAR_TERMS = {
    "sell": 1.0, "short": 1.1, "puts": 1.2, "bearish": 1.5, "overvalued": 1.4, "crash": 1.3,
    "dump": 1.1, "bubble": 1.2, "downside": 1.2, "miss": 1.0, "dilution": 1.3, "fraud": 1.5,
    "bankruptcy": 1.6, "overbought": 0.8, "rug": 1.3,
}
_DD_FLAIRS = ("dd", "due diligence", "discussion", "analysis", "research", "fundamentals")
_DD_MIN_BODY = 800

# Outlets whose coverage is more likely to be primary reporting than aggregation.
_TIER_ONE_DOMAINS = {
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com", "apnews.com",
    "barrons.com", "marketwatch.com", "nytimes.com", "businesswire.com", "prnewswire.com",
    "globenewswire.com", "sec.gov",
}

_WORD = re.compile(r"[a-z']+")


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _daily_counts(timestamps: Iterable[datetime], as_of: datetime, days: int) -> list[int]:
    """Counts per 24-hour bucket, oldest first, ending at as_of."""
    edges = [as_of - timedelta(days=offset) for offset in range(days, -1, -1)]
    buckets = [0] * days
    for stamp in timestamps:
        for index in range(days):
            if edges[index] <= stamp < edges[index + 1]:
                buckets[index] += 1
                break
    return buckets


def sentiment_ratio(texts: Sequence[str]) -> float:
    """Share of directional language that is bullish. 0.5 when there is none."""
    bull = 0.0
    bear = 0.0
    for text in texts:
        for token in _tokens(text):
            bull += _BULL_TERMS.get(token, 0.0) if _BULL_TERMS.get(token, 0.0) > 0 else 0.0
            bear += _BEAR_TERMS.get(token, 0.0)
    total = bull + bear
    if total <= 0:
        return 0.5
    return max(0.0, min(1.0, bull / total))


def dd_density(posts: Sequence[dict[str, Any]]) -> float:
    """Share of posts that carry actual argument rather than a one-liner."""
    if not posts:
        return 0.0
    substantive = sum(
        1
        for post in posts
        if post.get("body_length", 0) >= _DD_MIN_BODY
        or any(flair in str(post.get("flair", "")).lower() for flair in _DD_FLAIRS)
    )
    return round(substantive / len(posts), 4)


def novelty(recent_titles: Sequence[str], prior_titles: Sequence[str]) -> float:
    """How much of the recent coverage is genuinely new.

    Wire stories are republished verbatim across dozens of domains, so raw
    article counts overstate how much the world actually learned.
    """
    if not recent_titles:
        return 0.0
    prior_sets = [set(_tokens(title)) for title in prior_titles if title]
    fresh = 0
    seen: list[set[str]] = []
    for title in recent_titles:
        tokens = set(_tokens(title))
        if not tokens:
            continue
        duplicate = False
        for other in prior_sets + seen:
            if not other:
                continue
            overlap = len(tokens & other) / len(tokens | other)
            if overlap >= 0.6:
                duplicate = True
                break
        if not duplicate:
            fresh += 1
            seen.append(tokens)
    return round(min(1.0, fresh / len(recent_titles)), 4)


def catalyst_quality(
    filings: Sequence[dict[str, Any]],
    articles: Sequence[dict[str, Any]],
    as_of: datetime,
) -> float:
    """How well-evidenced the story is, independent of how loud it is."""
    score = 0.0
    recent_filings = [row for row in filings if as_of - row["created_at"] <= timedelta(hours=72)]
    if recent_filings:
        score += 0.55 if any(row["form"] in {"8-K", "6-K", "SC 13D", "13D"} for row in recent_filings) else 0.35
    domains = {str(row.get("domain", "")).lower() for row in articles}
    tier_one = len(domains & _TIER_ONE_DOMAINS)
    score += min(0.3, tier_one * 0.1)
    if len(domains) >= 5:
        score += 0.1
    return round(max(0.0, min(1.0, score)), 4)


def _returns(bars: Sequence[Bar]) -> list[float]:
    return [
        bars[index].close / bars[index - 1].close - 1.0
        for index in range(1, len(bars))
        if bars[index - 1].close > 0
    ]


def market_features(bars: Sequence[Bar]) -> dict[str, float]:
    """Price and volume abnormality from real bars.

    Returns zeroed values when there is not enough history to say anything,
    rather than manufacturing a z-score from three observations.
    """
    empty = {
        "market_z": 0.0,
        "relative_volume": 1.0,
        "abnormal_return_recent": 0.0,
        "pre_signal_return": 0.0,
    }
    if len(bars) < 8:
        return empty

    series = _returns(bars)
    if len(series) < 6:
        return empty

    latest_return = series[-1]
    history = series[-61:-1]
    volumes = [bar.volume for bar in bars[-21:-1] if bar.volume > 0]
    median_volume = statistics.median(volumes) if volumes else 0.0

    # Trailing return excluding the newest bar: how far it had already run
    # before this signal existed.
    window = bars[-6:-1]
    pre_signal = (window[-1].close / window[0].close - 1.0) if len(window) >= 2 and window[0].close > 0 else 0.0

    return {
        "market_z": round(robust_zscore(latest_return, history), 4),
        "relative_volume": round(bars[-1].volume / median_volume, 4) if median_volume > 0 else 1.0,
        "abnormal_return_recent": round(latest_return, 6),
        "pre_signal_return": round(pre_signal, 6),
    }


def build_features(
    *,
    posts: Sequence[dict[str, Any]],
    articles: Sequence[dict[str, Any]],
    news_timeline: Sequence[tuple[datetime, float]],
    bars: Sequence[Bar],
    filings: Sequence[dict[str, Any]],
    as_of: datetime | None = None,
    price_resolution: str = "1Day",
    window_days: int = 7,
) -> SignalFeatures:
    """Compute the full feature vector from live observations.

    Every value here is derived from something that was actually fetched. A leg
    with no data produces neutral values, never invented ones.
    """
    as_of = as_of or datetime.now(UTC)
    day_ago = as_of - timedelta(days=1)

    recent_posts = [post for post in posts if post["created_at"] >= day_ago]
    social_daily = _daily_counts((post["created_at"] for post in posts), as_of, window_days)
    social_recent = social_daily[-1] if social_daily else 0
    social_history = social_daily[:-1]
    prior_mean = statistics.fmean(social_history) if social_history else 0.0

    recent_articles = [row for row in articles if row["created_at"] >= day_ago]
    prior_articles = [row for row in articles if row["created_at"] < day_ago]

    if len(news_timeline) >= 6:
        values = [value for _, value in news_timeline]
        news_z = robust_zscore(values[-1], values[:-1])
    else:
        news_daily = _daily_counts((row["created_at"] for row in articles), as_of, window_days)
        news_z = robust_zscore(news_daily[-1], news_daily[:-1]) if news_daily else 0.0

    price = market_features(bars)
    social_z = robust_zscore(social_recent, social_history)
    authors = {post["author"] for post in recent_posts if post["author"] != "[deleted]"}

    return SignalFeatures(
        social_count=len(recent_posts),
        unique_authors=len(authors),
        social_acceleration=round(social_recent / prior_mean, 4) if prior_mean > 0 else (1.0 if social_recent == 0 else 3.0),
        social_z=round(social_z, 4),
        dd_density=dd_density(recent_posts),
        bull_ratio=round(sentiment_ratio([f"{post['title']} {post['body']}" for post in recent_posts]), 4),
        news_count=len(recent_articles),
        news_z=round(news_z, 4),
        catalyst_quality=catalyst_quality(filings, recent_articles, as_of),
        novelty=novelty([row["title"] for row in recent_articles], [row["title"] for row in prior_articles]),
        filing_confirmed=any(as_of - row["created_at"] <= timedelta(hours=72) for row in filings),
        market_z=price["market_z"],
        relative_volume=max(0.0, price["relative_volume"]),
        abnormal_return_recent=price["abnormal_return_recent"],
        price_resolution=price_resolution,
        pre_signal_return=price["pre_signal_return"],
        social_news_gap=round(social_z - news_z, 4),
        social_price_gap=round(social_z - price["market_z"], 4),
        news_price_gap=round(news_z - price["market_z"], 4),
        already_pumped_penalty=round(already_pumped_penalty(price["pre_signal_return"], price["market_z"]), 4),
    )


def top_subreddits(posts: Sequence[dict[str, Any]], limit: int = 3) -> list[tuple[str, int]]:
    """Where the conversation is actually happening."""
    counter = Counter(post["subreddit"] for post in posts if post.get("subreddit"))
    return counter.most_common(limit)
