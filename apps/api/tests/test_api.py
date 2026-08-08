from __future__ import annotations

import importlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ape_alpha import config as config_module
from ape_alpha.api import app
from ape_alpha.sources import sec

resolve_module = importlib.import_module("ape_alpha.research.resolve")

client = TestClient(app)


@pytest.fixture(autouse=True)
def offline_universe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve a fixed listing universe so no test reaches the network."""

    async def fake_universe() -> dict[str, dict[str, Any]]:
        return {
            "ASTS": {"ticker": "ASTS", "company": "AST SpaceMobile, Inc.", "cik": 1780312},
            "AAPL": {"ticker": "AAPL", "company": "Apple Inc.", "cik": 320193},
            "ALL": {"ticker": "ALL", "company": "Allstate Corp", "cik": 899051},
        }

    monkeypatch.setattr(sec, "load_universe", fake_universe)
    monkeypatch.setattr(resolve_module, "load_universe", fake_universe)
    sec.reset_universe_cache()


def test_health_reports_which_credentials_are_present() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "paper-research"
    assert set(body["credentials"]) == {"reddit", "webcmd", "alpaca", "openai"}


def test_source_health_lists_every_leg_with_a_status() -> None:
    sources = client.get("/api/v1/source-health").json()["sources"]
    names = {item["source"] for item in sources}
    assert {
        "WebCMD Reddit",
        "WebCMD X",
        "WebCMD Google News",
        "WebCMD Yahoo News",
        "Reddit API fallback",
        "GDELT news",
        "SEC EDGAR",
        "Market bars",
        "OpenAI analysis",
    } <= names
    assert all(item["status"] in {"ready", "unavailable"} for item in sources)


def test_keyless_sources_are_always_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    config_module.reset_settings()
    sources = {item["source"]: item for item in client.get("/api/v1/source-health").json()["sources"]}
    assert sources["GDELT news"]["status"] == "ready"
    assert sources["SEC EDGAR"]["status"] == "ready"
    assert sources["Market bars"]["status"] == "ready"
    assert sources["Reddit API fallback"]["status"] == "unavailable"
    config_module.reset_settings()


def test_resolve_matches_a_symbol_and_a_company_name() -> None:
    by_symbol = client.get("/api/v1/resolve", params={"q": "ASTS"}).json()["candidates"]
    assert by_symbol[0]["ticker"] == "ASTS"
    assert by_symbol[0]["matchedOn"] == "symbol"

    by_name = client.get("/api/v1/resolve", params={"q": "apple"}).json()["candidates"]
    assert by_name[0]["ticker"] == "AAPL"
    assert by_name[0]["matchedOn"] == "company_name"


def test_ambiguous_english_words_need_a_cashtag() -> None:
    bare = client.get("/api/v1/resolve", params={"q": "ALL"}).json()["candidates"]
    assert all(item["matchedOn"] != "symbol" for item in bare)

    cashtagged = client.get("/api/v1/resolve", params={"q": "$ALL"}).json()["candidates"]
    assert cashtagged[0]["ticker"] == "ALL"
    assert cashtagged[0]["matchedOn"] == "symbol"


def test_unresolvable_query_returns_no_candidates() -> None:
    body = client.get("/api/v1/resolve", params={"q": "zzzqqxnotacompany"}).json()
    assert body["candidates"] == []


def test_research_rejects_an_empty_query() -> None:
    assert client.post("/api/v1/research", json={"query": ""}).status_code == 422


def test_paper_approval_never_creates_live_order() -> None:
    response = client.post("/api/v1/paper-orders/demo/approve?ticker=asts&requested_nav_pct=0.005")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "paper"
    assert body["ticker"] == "ASTS"
    assert body["approved_nav_pct"] <= 0.01


def test_paper_approval_caps_oversized_requests() -> None:
    response = client.post("/api/v1/paper-orders/demo/approve?ticker=ASTS&requested_nav_pct=0.5")
    assert response.status_code == 422
