from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .backfill import backfill_ticker
from .backtest import persist_backtest, run_backtest
from .config import ENV_FILE, settings
from .contracts import ResearchResult, TradeIntent
from .markets import PROFILES, Market
from .repository import load_json, project_root
from .research.engine import UnresolvedQuery, research
from .research.resolve import resolve
from .sources.http import SourceError
from .sources.webcmd import configured as webcmd_configured, installed_commands
from .store import append_snapshots, read_manifest, read_snapshots, row_from_result

app = FastAPI(title="APE Alpha Research API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=120)
    market: Market = Market.US
    use_llm: bool = True
    record: bool = True


class BackfillRequest(BaseModel):
    query: str = Field(min_length=1, max_length=120)
    market: Market = Market.US
    lookback_days: int = Field(default=365, ge=60, le=1825)


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    config = settings()
    return {
        "status": "ok",
        "mode": "paper-research",
        "time": datetime.now(UTC).isoformat(),
        "envFile": str(ENV_FILE) if ENV_FILE else None,
        "credentials": {
            "reddit": config.reddit_enabled,
            "webcmd": webcmd_configured(),
            "alpaca": config.alpaca_enabled,
            "openai": config.openai_enabled,
        },
    }


@app.get("/api/v1/resolve")
async def resolve_query(
    q: str = Query(min_length=1, max_length=120), market: Market = Market.US
) -> dict[str, Any]:
    """Candidate securities for a free-text query, best first."""
    try:
        candidates = await resolve(q, market=market)
    except SourceError as exc:
        raise HTTPException(503, exc.detail) from exc
    return {
        "query": q,
        "candidates": [
            {
                "ticker": item.ticker,
                "displaySymbol": item.display_symbol,
                "market": item.market.value,
                "company": item.company,
                "cik": item.cik,
                "confidence": item.confidence,
                "matchedOn": item.matched_on,
            }
            for item in candidates
        ],
    }


@app.post("/api/v1/research", response_model=ResearchResult)
async def run_research(request: ResearchRequest) -> ResearchResult:
    """Run every live source against one query.

    The result is appended to the point-in-time store by default, which is what
    grows the forward record the backtest later evaluates.
    """
    try:
        result = await research(request.query, market=request.market, use_llm=request.use_llm)
    except UnresolvedQuery as exc:
        raise HTTPException(
            404,
            {
                "message": f"Could not resolve {exc.query!r} to a listing on the {request.market.value} market.",
                "candidates": [item.ticker for item in exc.candidates],
            },
        ) from exc
    except SourceError as exc:
        raise HTTPException(503, exc.detail) from exc

    if request.record:
        append_snapshots(project_root(), [row_from_result(result)])
    return result


@app.get("/api/v1/watchlist")
def watchlist(limit: int = Query(default=12, ge=1, le=100)) -> dict[str, Any]:
    """The most recent live observation per ticker in the store."""
    rows = [row for row in read_snapshots(project_root()) if row["origin"] == "live"]
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest[row["ticker"]] = row
    ordered = sorted(latest.values(), key=lambda item: item["as_of"], reverse=True)[:limit]
    return {"manifest": read_manifest(project_root()), "tickers": ordered}


@app.get("/api/v1/markets")
def markets() -> dict[str, Any]:
    """Supported listing venues and what each one is measured against."""
    return {
        "markets": [
            {
                "market": item.market.value,
                "label": item.label,
                "currency": item.currency,
                "benchmark": item.benchmark,
                "benchmarkLabel": item.benchmark_label,
                "filings": item.filing_label,
                "subreddits": list(item.subreddits),
            }
            for item in PROFILES.values()
        ]
    }


@app.get("/api/v1/manifest")
def manifest() -> dict[str, Any]:
    return read_manifest(project_root())


@app.get("/api/v1/source-health")
async def source_health() -> dict[str, Any]:
    """What each acquisition leg can currently do, before any query is run."""
    config = settings()
    commands: set[str] = set()
    webcmd_error = ""
    try:
        commands = await installed_commands()
    except (SourceError, SourceUnavailable) as exc:
        webcmd_error = exc.detail
    return {
        "sources": [
            {
                "source": "WebCMD Reddit",
                "status": "ready" if "reddit/search" in commands else "unavailable",
                "detail": "On-demand browser-session search; login is verified on each research run"
                if "reddit/search" in commands
                else webcmd_error or "Install the Reddit WebCMD adapter",
            },
            {
                "source": "WebCMD X",
                "status": "ready" if "twitter/search" in commands else "unavailable",
                "detail": "On-demand X search through the authorized WebCMD browser session"
                if "twitter/search" in commands
                else webcmd_error or "Install the Twitter WebCMD adapter",
            },
            {
                "source": "WebCMD Google News",
                "status": "ready" if "ape-alpha/google-news" in commands else "unavailable",
                "detail": "On-demand locale-aware current news via public RSS"
                if "ape-alpha/google-news" in commands
                else webcmd_error or "Install the APE Alpha WebCMD plugin",
            },
            {
                "source": "WebCMD Yahoo News",
                "status": "ready" if "ape-alpha/yahoo-news" in commands else "unavailable",
                "detail": "On-demand ticker-related Yahoo Finance stories"
                if "ape-alpha/yahoo-news" in commands
                else webcmd_error or "Install the APE Alpha WebCMD plugin",
            },
            {
                "source": "Reddit API fallback",
                "status": "ready" if config.reddit_enabled else "unavailable",
                "detail": "Approved OAuth fallback"
                if config.reddit_enabled
                else "Optional: set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET",
            },
            {"source": "GDELT news", "status": "ready", "detail": "Keyless, historical archive from 2017"},
            {"source": "SEC EDGAR", "status": "ready", "detail": "Keyless — US filings, acceptance timestamps"},
            {"source": "NSE announcements", "status": "ready", "detail": "Keyless — India corporate filings"},
            {
                "source": "Market bars",
                "status": "ready",
                "detail": "Alpaca IEX 1-hour bars"
                if config.alpaca_enabled
                else "Yahoo daily — set ALPACA_API_KEY for intraday",
            },
            {
                "source": "OpenAI analysis",
                "status": "ready" if config.openai_enabled else "unavailable",
                "detail": f"Narrative, sentiment and evidence interpretation via {config.openai_model}"
                if config.openai_enabled
                else "Set OPENAI_API_KEY to enable the AI analysis layer",
            },
        ]
    }


@app.post("/api/v1/backfill")
async def create_backfill(request: BackfillRequest) -> dict[str, Any]:
    """Reconstruct real historical news and price observations for one security."""
    try:
        return await backfill_ticker(
            project_root(), request.query, market=request.market, lookback_days=request.lookback_days
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except SourceError as exc:
        raise HTTPException(503, exc.detail) from exc


@app.post("/api/v1/backtests")
async def create_backtest(locked: bool = False) -> dict[str, Any]:
    root = project_root()
    run = await run_backtest(root, locked=locked)
    persist_backtest(root, run)
    return json.loads(run.model_dump_json())


@app.get("/api/v1/backtests/latest")
def latest_backtest() -> dict[str, Any]:
    try:
        return load_json("backtest.json")
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/v1/paper-orders/{intent_id}/approve", response_model=TradeIntent)
def approve_paper_order(intent_id: str, ticker: str, requested_nav_pct: float = 0.005) -> TradeIntent:
    """Paper only. There is no code path from here to a broker."""
    # The 1% NAV ceiling is a risk limit, so a request above it is rejected
    # outright rather than quietly clamped — silently approving something
    # smaller than what was asked for is how limits get misread as advisory.
    if not 0 < requested_nav_pct <= 0.01:
        raise HTTPException(422, "requested_nav_pct must be greater than 0 and at most 0.01 (1% of NAV).")
    approved = min(requested_nav_pct, 0.01)
    return TradeIntent(
        intent_id=intent_id,
        ticker=ticker.upper(),
        requested_nav_pct=requested_nav_pct,
        approved_nav_pct=approved,
        risk_status="approved",
        human_status="approved",
        reason="Paper-only intent approved within the 1% NAV deterministic cap.",
    )


def main() -> None:
    uvicorn.run("ape_alpha.api:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
