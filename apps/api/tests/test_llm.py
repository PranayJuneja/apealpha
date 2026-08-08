from __future__ import annotations

import json
from typing import Any

import pytest

from ape_alpha.contracts import NarrativePhase, SignalFeatures
from ape_alpha.research import llm


def features() -> SignalFeatures:
    return SignalFeatures(
        social_count=14,
        unique_authors=10,
        social_acceleration=2.0,
        social_z=2.4,
        dd_density=0.4,
        bull_ratio=0.72,
        news_count=4,
        news_z=0.8,
        catalyst_quality=0.6,
        novelty=0.75,
        filing_confirmed=True,
        market_z=0.3,
        relative_volume=1.2,
        abnormal_return_recent=0.01,
        pre_signal_return=0.02,
        social_news_gap=1.6,
        social_price_gap=2.1,
        news_price_gap=0.5,
        already_pumped_penalty=0.0,
    )


def test_rules_understanding_is_available_without_an_api() -> None:
    result = llm.rules_understanding("PLTR", features(), NarrativePhase.WHISPER)
    assert result.source == "rules"
    assert result.sentiment == "bullish"
    assert result.drivers


@pytest.mark.asyncio
async def test_openai_analysis_uses_luna_and_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class Config:
        openai_enabled = True
        openai_api_key = "test-key"
        openai_model = "gpt-5.6-luna"
        openai_reasoning_effort = "low"
        openai_timeout_seconds = 45.0

    async def fake_request(*_: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs["json_body"])
        return {
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": json.dumps({
                        "narrative": "Social attention is ahead of measured news coverage.",
                        "sentiment": "bullish",
                        "confidence": 0.78,
                        "summary": "Social attention leads measured news coverage.",
                        "drivers": ["Social is elevated"],
                        "risks": ["Coverage is incomplete"],
                    }),
                }],
            }],
        }

    monkeypatch.setattr(llm, "settings", lambda: Config())
    monkeypatch.setattr(llm, "request_json", fake_request)
    narrative, result = await llm.openai_analysis(
        "PLTR", "Palantir", features(), NarrativePhase.WHISPER, ["$PLTR post"]
    )
    assert captured["model"] == "gpt-5.6-luna"
    assert captured["text"]["format"]["type"] == "json_schema"
    assert "Social attention" in narrative
    assert result.source == "openai"
    assert result.sentiment == "bullish"
