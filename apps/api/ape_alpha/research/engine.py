from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Any, Callable, Sequence

from ..config import settings
from ..contracts import (
    NarrativePhase,
    ResearchResult,
    SignalFeatures,
    SignalSnapshot,
    SourceEvent,
    SourceStatus,
    SourceType,
)
from ..markets import Market
from ..signals import CLASSIFIER_VERSION, SIGNAL_VERSION, classify_phase, phase_confidence
from ..sources import live_news as live_news_source
from ..sources import market as market_source
from ..sources import news as news_source
from ..sources import nse as nse_source
from ..sources import social as social_source
from ..sources import sec as sec_source
from ..sources.http import SourceError, SourceUnavailable
from .features import build_features
from .llm import openai_analysis, rules_narrative, rules_understanding
from .playbook import build_playbook
from .resolve import Resolution, resolve

DATASET_VERSION = "live-acquisition-v5-webcmd-reddit-x-news"

# Per-source wall-clock budget. Sources are fetched concurrently, so without a
# cap the slowest one sets the latency of the whole run — and GDELT in
# particular can spend a long time in connect-timeout retries when throttled.
# Exceeding the budget degrades that leg; it never fails the request.
SOURCE_BUDGET_SECONDS = 25.0


class UnresolvedQuery(LookupError):
    """The query did not match a listed US security."""

    def __init__(self, query: str, candidates: Sequence[Resolution]) -> None:
        super().__init__(f"Could not resolve {query!r} to a listed security")
        self.query = query
        self.candidates = list(candidates)


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _event(
    source_type: SourceType,
    ticker: str,
    title: str,
    url: str,
    created_at: datetime,
    ingested_at: datetime,
    confidence: float,
    metadata: dict[str, Any],
) -> SourceEvent:
    content_hash = _digest(source_type.value, url, title, created_at.isoformat())
    return SourceEvent(
        event_id=f"{source_type.value}_{content_hash[:20]}",
        source_type=source_type,
        ticker=ticker,
        title=title or "(untitled)",
        source_url=url,
        source_created_at=created_at,
        source_first_seen_at=created_at,
        ingested_at=ingested_at,
        ticker_confidence=confidence,
        raw_content_hash=content_hash,
        metadata=metadata,
    )


async def _budgeted(coro: Any) -> Any:
    """Run a source fetch under the shared budget."""
    return await asyncio.wait_for(coro, timeout=SOURCE_BUDGET_SECONDS)


# Progress events are one-way notifications for a UI; they never change the
# result. Keys name acquisition legs as the frontend presents them.
ProgressFn = Callable[[dict[str, Any]], None]


def _result_count(result: Any) -> int:
    if isinstance(result, social_source.SocialFetch):
        return len(result.posts)
    if isinstance(result, live_news_source.NewsFetch):
        return len(result.articles)
    if isinstance(result, tuple):  # (bars, provider)
        return len(result[0])
    if isinstance(result, (list, tuple)):
        return len(result)
    return 0


async def _traced(key: str, coro: Any, emit: ProgressFn) -> Any:
    """Run one budgeted source fetch, reporting start and outcome.

    Mirrors gather(return_exceptions=True): exceptions are returned, not
    raised, so downstream unwrapping stays unchanged.
    """
    emit({"type": "source_start", "key": key})
    try:
        result = await _budgeted(coro)
    except BaseException as exc:  # noqa: BLE001 - handed to _unwrap downstream
        detail = str(getattr(exc, "detail", "") or type(exc).__name__)
        emit({"type": "source_done", "key": key, "ok": False, "detail": detail})
        return exc
    emit({"type": "source_done", "key": key, "ok": True, "count": _result_count(result)})
    return result


def _unwrap(result: Any, source: str, provider: str = "") -> tuple[Any, SourceStatus]:
    """Turn a gather result into data plus an honest status line."""
    if isinstance(result, SourceUnavailable):
        return None, SourceStatus(source=source, status="unavailable", provider=provider, detail=result.detail)
    if isinstance(result, SourceError):
        return None, SourceStatus(source=source, status="degraded", provider=provider, detail=result.detail)
    if isinstance(result, (TimeoutError, asyncio.TimeoutError)):
        return None, SourceStatus(
            source=source,
            status="degraded",
            provider=provider,
            detail=f"did not answer within {SOURCE_BUDGET_SECONDS:.0f}s",
        )
    if isinstance(result, BaseException):
        return None, SourceStatus(
            source=source, status="degraded", provider=provider, detail=f"unexpected {type(result).__name__}"
        )
    count = len(result) if isinstance(result, (list, tuple)) else 0
    return result, SourceStatus(source=source, status="live", provider=provider, events=count)


def merge_articles(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine news providers, dropping the same story seen twice.

    Google News and GDELT overlap heavily on major stories. Counting a story
    once per provider would inflate news volume and shrink the narrative gap
    for exactly the securities that are most covered.
    """
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for article in group or []:
            title = str(article.get("title", "")).strip().lower()
            # Same headline within a day is the same story, wherever it came from.
            key = f"{title}|{article['created_at'].date().isoformat()}"
            if key and key not in merged:
                merged[key] = article
    return sorted(merged.values(), key=lambda row: row["created_at"])


def detect_conflict(features: SignalFeatures, posts_scored: int) -> bool:
    """Do the sources actually disagree?

    Two shapes count. Either the crowd is split down the middle while talking a
    lot, or social enthusiasm is pointing the opposite way to a decisive price
    move. Both mean the narrative is contested, and a contested narrative is not
    something to size into.
    """
    split_crowd = posts_scored >= 12 and 0.42 <= features.bull_ratio <= 0.58
    against_tape = features.social_z >= 2.0 and features.bull_ratio >= 0.65 and features.market_z <= -2.0
    return bool(split_crowd or against_tape)


async def research(
    query: str,
    *,
    market: Market | str = Market.US,
    as_of: datetime | None = None,
    use_llm: bool = True,
    emit: ProgressFn | None = None,
) -> ResearchResult:
    """Run every live source against one query and return a complete result.

    Sources are fetched concurrently and failures are isolated: a dark social
    leg degrades the answer and is reported as such, but still produces news,
    filing and price analysis rather than an error page.
    """
    emit = emit or (lambda event: None)
    as_of = as_of or datetime.now(UTC)
    emit({"type": "resolve_start", "query": query})
    candidates = await resolve(query, market=market, as_of=as_of.date())
    if not candidates:
        raise UnresolvedQuery(query, [])
    best = candidates[0]
    profile = best.profile
    emit(
        {
            "type": "resolved",
            "ticker": best.display_symbol,
            "company": best.company,
            "market": best.market.value,
            "confidence": best.confidence,
        }
    )

    filings_call = (
        sec_source.fetch_filings(best.cik)
        if profile.filing_source == "sec"
        else nse_source.fetch_announcements(best.ticker)
    )
    requested_price_resolution = "1Hour" if settings().alpaca_enabled else "1Day"

    fetched = await asyncio.gather(
        _traced(
            "social",
            social_source.fetch_mentions(
                best.display_symbol, best.company, subreddits=profile.subreddits
            ),
            emit,
        ),
        _traced(
            "news_archive",
            news_source.fetch_articles(best.display_symbol, best.company, timespan="7d"),
            emit,
        ),
        _traced(
            "news_baseline",
            news_source.fetch_volume_timeline(best.display_symbol, best.company),
            emit,
        ),
        _traced(
            "price",
            market_source.fetch_bars(
                best.ticker,
                lookback_days=180,
                timeframe=requested_price_resolution,
            ),
            emit,
        ),
        _traced("filings", filings_call, emit),
        _traced(
            "news_current",
            live_news_source.fetch_articles(best.display_symbol, best.company, profile),
            emit,
        ),
        return_exceptions=True,
    )

    social_result = fetched[0]
    if isinstance(social_result, social_source.SocialFetch):
        posts = social_result.posts
        social_status = SourceStatus(
            source="social",
            status="live",
            provider=social_result.provider,
            events=len(posts),
            detail=social_result.detail,
        )
    else:
        posts, social_status = _unwrap(social_result, "social", "webcmd-x + webcmd-reddit + reddit-oauth")
    gdelt_articles, gdelt_status = _unwrap(fetched[1], "news", "gdelt")
    timeline_result = fetched[2]
    timeline = timeline_result if isinstance(timeline_result, list) else []
    filings, filing_status = _unwrap(fetched[4], "filings", profile.filing_source)
    live_news_result = fetched[5]
    if isinstance(live_news_result, live_news_source.NewsFetch):
        current_articles = live_news_result.articles
        current_news_status = SourceStatus(
            source="news",
            status="live",
            provider=live_news_result.provider,
            events=len(current_articles),
            detail=live_news_result.detail,
        )
    else:
        current_articles, current_news_status = _unwrap(
            live_news_result, "news", "webcmd-google-news + webcmd-yahoo-news"
        )

    bars: list[market_source.Bar] = []
    price_provider = ""
    if isinstance(fetched[3], BaseException):
        _, price_status = _unwrap(fetched[3], "price")
    else:
        bars, price_provider = fetched[3]
        actual_price_resolution = (
            requested_price_resolution if price_provider == "alpaca" else "1Day"
        )
        price_status = SourceStatus(
            source="price",
            status="live",
            provider=price_provider,
            events=len(bars),
            detail=f"{actual_price_resolution} bars via {price_provider}",
        )

    posts = posts or []
    filings = filings or []
    articles = merge_articles(gdelt_articles or [], current_articles or [])

    # The news leg is live if either provider answered; the detail records which
    # ones did, because they contribute different things — Google supplies
    # recency and locale, GDELT supplies the historical baseline.
    providers = [
        name
        for name, status in (("gdelt", gdelt_status), ("webcmd-current-news", current_news_status))
        if status.status == "live"
    ]
    if providers:
        detail = f"{' + '.join(providers)}"
        if not timeline:
            detail += "; no volume baseline, news z-score from daily counts"
        news_status = SourceStatus(
            source="news", status="live", provider=" + ".join(providers),
            events=len(articles), detail=f"{detail}; {current_news_status.detail}" if current_news_status.detail else detail,
        )
    else:
        news_status = SourceStatus(
            source="news", status="degraded", provider="gdelt + webcmd-current-news",
            detail=f"gdelt: {gdelt_status.detail}; webcmd news: {current_news_status.detail}",
        )

    features = build_features(
        posts=posts,
        articles=articles,
        news_timeline=timeline,
        bars=bars,
        filings=filings,
        as_of=as_of,
        price_resolution=(
            requested_price_resolution if price_provider == "alpaca" else "1Day"
        ),
    )

    coverage = [social_status, news_status, filing_status, price_status]
    # The phase model is a statement about social lead or lag. If the social leg
    # did not answer, there is no such statement to make.
    social_live = social_status.status == "live"
    phase = classify_phase(features) if social_live else NarrativePhase.INDETERMINATE
    conflict = detect_conflict(features, len(posts)) if social_live else False
    playbook = build_playbook(features, phase, coverage, conflict=conflict)
    emit(
        {
            "type": "classified",
            "phase": phase.value,
            "stance": playbook.stance,
            "social_z": features.social_z,
            "news_z": features.news_z,
            "market_z": features.market_z,
            "gap": features.social_news_gap,
        }
    )

    ingested_at = datetime.now(UTC)
    events: list[SourceEvent] = []
    for post in posts:
        events.append(
            _event(
                SourceType.SOCIAL, best.display_symbol, post["title"], post["url"], post["created_at"], ingested_at, 0.9,
                {
                    "platform": post.get("platform", "reddit"),
                    "community": post.get("community", post.get("subreddit", "")),
                    "subreddit": post.get("subreddit", ""),
                    "author": post["author"],
                    "score": post["score"],
                    "comments": post["comments"],
                    "flair": post["flair"],
                    "views": post.get("views", 0),
                    "has_media": post.get("has_media", False),
                },
            )
        )
    for article in articles:
        events.append(
            _event(
                SourceType.NEWS, best.display_symbol, article["title"], article["url"], article["created_at"], ingested_at, 1.0,
                {
                    "domain": article["domain"],
                    "language": article["language"],
                    "country": article["country"],
                    "provider": article.get("provider", "gdelt"),
                },
            )
        )
    for filing in filings:
        events.append(
            _event(
                SourceType.FILING, best.display_symbol, f"{filing['form']} filed", filing["url"], filing["created_at"],
                ingested_at, 1.0, {"form": filing["form"], "accession": filing["accession"]},
            )
        )
    if bars:
        latest = bars[-1]
        bar_label = "Close" if features.price_resolution == "1Day" else f"Last {features.price_resolution} bar"
        events.append(
            _event(
                SourceType.MARKET, best.display_symbol,
                f"{bar_label} {latest.close:.2f} on {features.relative_volume:.2f}× median volume",
                f"https://finance.yahoo.com/quote/{best.ticker}", latest.at, ingested_at, 1.0,
                {
                    "provider": price_provider,
                    "resolution": features.price_resolution,
                    "volume": latest.volume,
                    "close": latest.close,
                },
            )
        )
    events.sort(key=lambda item: item.source_created_at)

    action = "NO_TRADE" if playbook.stance == "STAND_ASIDE" else ("PAPER_BUY" if playbook.stance == "PAPER_LONG" else "WATCH")
    snapshot = SignalSnapshot(
        snapshot_id=f"sig_{_digest(best.ticker, as_of.isoformat(), SIGNAL_VERSION)[:20]}",
        ticker=best.ticker,
        company=best.company,
        signal_generated_at=as_of,
        phase=phase,
        conflict=conflict,
        confidence=phase_confidence(features, phase),
        features=features,
        evidence_event_ids=[event.event_id for event in events],
        classifier_version=CLASSIFIER_VERSION,
        signal_version=SIGNAL_VERSION,
        dataset_version=DATASET_VERSION,
        thesis=playbook.rationale,
        action=action,
    )

    narrative = rules_narrative(best.ticker, best.company, features, phase, playbook)
    narrative_source: str = "rules"
    understanding = rules_understanding(best.ticker, features, phase)
    analysis_warning = ""
    if use_llm:
        emit(
            {
                "type": "analysis_start",
                "evidence": min(len(posts), 12) + min(len(articles), 8),
            }
        )
        try:
            narrative, understanding = await openai_analysis(
                best.ticker,
                best.company,
                features,
                phase,
                [post["body"] for post in posts[-12:]]
                + [article["title"] for article in articles[-8:]],
            )
            narrative_source = "openai"
            emit({"type": "analysis_done", "ok": True, "sentiment": understanding.sentiment})
        except (SourceError, KeyError, ValueError) as exc:
            analysis_warning = f"OpenAI analysis: {exc.detail if isinstance(exc, SourceError) else 'invalid response'}"
            emit({"type": "analysis_done", "ok": False})

    warnings: list[str] = []
    if analysis_warning:
        warnings.append(analysis_warning)
    if best.confidence < 0.9:
        others = ", ".join(f"{item.ticker} ({item.company})" for item in candidates[1:4])
        warnings.append(
            f"{query!r} matched {best.ticker} on company name at {best.confidence:.0%} confidence."
            + (f" Other candidates: {others}." if others else "")
        )
    for status in coverage:
        if status.status != "live":
            warnings.append(f"{status.source}: {status.status} — {status.detail}")

    return ResearchResult(
        query=query,
        ticker=best.ticker,
        display_symbol=best.display_symbol,
        market=best.market.value,
        market_label=profile.label,
        currency=profile.currency,
        company=best.company,
        cik=best.cik,
        resolution_confidence=best.confidence,
        generated_at=as_of,
        snapshot=snapshot,
        playbook=playbook,
        events=events,
        coverage=coverage,
        narrative=narrative,
        narrative_source=narrative_source,  # type: ignore[arg-type]
        understanding=understanding,
        warnings=warnings,
    )
