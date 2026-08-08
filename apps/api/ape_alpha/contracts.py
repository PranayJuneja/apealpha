from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    SOCIAL = "social"
    NEWS = "news"
    FILING = "filing"
    IR = "ir"
    MARKET = "market"


class NarrativePhase(str, Enum):
    WHISPER = "WHISPER"
    CONFIRMED = "CONFIRMED"
    MANIA = "MANIA"
    EXIT_LIQUIDITY = "EXIT_LIQUIDITY"
    # Every other phase is a claim about where social attention sits relative to
    # news and price. With the social leg dark, social_z is an unmeasured zero,
    # not a quiet crowd — and calling that WHISPER would invert the finding.
    INDETERMINATE = "INDETERMINATE"


class SourceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    source_type: SourceType
    ticker: str = Field(pattern=r"^[A-Z][A-Z0-9.\-]{0,9}$")
    title: str
    source_url: str
    source_created_at: datetime
    source_first_seen_at: datetime
    ingested_at: datetime
    ticker_confidence: float = Field(ge=0, le=1)
    raw_content_hash: str = Field(min_length=16)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceStatus(BaseModel):
    """What one acquisition leg actually delivered on this run.

    A signal computed with a dark source is not the same object as one computed
    with all three, so coverage travels with the snapshot rather than being
    inferred from the numbers.
    """

    model_config = ConfigDict(extra="forbid")

    source: str
    status: Literal["live", "degraded", "unavailable"]
    provider: str = ""
    events: int = 0
    detail: str = ""


class SignalFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    social_count: int = Field(ge=0)
    unique_authors: int = Field(ge=0)
    social_acceleration: float
    social_z: float
    dd_density: float = Field(ge=0, le=1)
    bull_ratio: float = Field(ge=0, le=1)
    news_count: int = Field(ge=0)
    news_z: float
    catalyst_quality: float = Field(ge=0, le=1)
    novelty: float = Field(ge=0, le=1)
    filing_confirmed: bool
    market_z: float
    relative_volume: float = Field(ge=0)
    abnormal_return_recent: float
    price_resolution: str = "1Day"
    pre_signal_return: float
    social_news_gap: float
    social_price_gap: float
    news_price_gap: float
    already_pumped_penalty: float = Field(ge=0, le=1)


class Playbook(BaseModel):
    """A rules-based paper-trade plan.

    Every field is a rule the engine can evaluate later, not a recommendation.
    Sizing is capped deterministically and there is no live execution path.
    """

    model_config = ConfigDict(extra="forbid")

    stance: Literal["PAPER_LONG", "WATCH", "STAND_ASIDE"]
    rationale: str
    entry_trigger: str
    invalidation: str
    time_stop_hours: int
    max_nav_pct: float = Field(ge=0, le=0.01)
    expected_holding_period: str
    risks: list[str]


class SignalSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    ticker: str
    company: str
    signal_generated_at: datetime
    phase: NarrativePhase
    conflict: bool
    confidence: float = Field(ge=0, le=1)
    features: SignalFeatures
    evidence_event_ids: list[str]
    classifier_version: str
    signal_version: str
    dataset_version: str
    thesis: str
    action: Literal["WATCH", "PAPER_BUY", "NO_TRADE"]


class AIUnderstanding(BaseModel):
    """A final evidence interpretation, separate from deterministic scoring."""

    model_config = ConfigDict(extra="forbid")

    sentiment: Literal["strongly_bearish", "bearish", "mixed", "bullish", "strongly_bullish"]
    confidence: float = Field(ge=0, le=1)
    summary: str
    drivers: list[str] = Field(default_factory=list, max_length=4)
    risks: list[str] = Field(default_factory=list, max_length=4)
    source: Literal["openai", "rules"] = "rules"
    model: str = "deterministic"


class ResearchResult(BaseModel):
    """Everything one live run produced, including what it could not see."""

    model_config = ConfigDict(extra="forbid")

    query: str
    ticker: str
    display_symbol: str
    market: str
    market_label: str
    currency: str
    company: str
    cik: int
    resolution_confidence: float
    generated_at: datetime
    snapshot: SignalSnapshot
    playbook: Playbook
    events: list[SourceEvent]
    coverage: list[SourceStatus]
    narrative: str = ""
    narrative_source: Literal["rules", "openai"] = "rules"
    understanding: AIUnderstanding
    warnings: list[str] = Field(default_factory=list)


class BacktestConfig(BaseModel):
    training_months: int = 6
    evaluation_months: int = 1
    holdout_fraction: float = 0.2
    transaction_cost_bps_per_side: float = 10
    max_bar_participation: float = 0.01
    reentry_cooldown_hours: int = 24
    primary_horizon: str = "1d"
    bootstrap_samples: int = 500
    seed: int = 7411


class StrategyResult(BaseModel):
    strategy: str
    signals: int
    win_rate: float
    mean_excess_return: float
    confidence_interval: tuple[float, float]
    total_return: float
    max_drawdown: float
    turnover: float
    false_positive_rate: float


class SourceCoverage(BaseModel):
    """Per-source honesty about what the backtest was actually run on."""

    source: str
    mode: Literal["historical", "forward_only", "unavailable"]
    first_observation: datetime | None = None
    last_observation: datetime | None = None
    observations: int = 0
    detail: str = ""


class BacktestRun(BaseModel):
    run_id: str
    dataset_version: str
    dataset_label: str
    configuration_hash: str
    code_version: str
    started_at: datetime
    completed_at: datetime
    locked_holdout: bool
    status: Literal["completed", "failed"]
    strategies: list[StrategyResult]
    coverage: list[SourceCoverage] = Field(default_factory=list)
    caveats: list[str]


class TradeIntent(BaseModel):
    intent_id: str
    ticker: str
    mode: Literal["paper"] = "paper"
    requested_nav_pct: float = Field(gt=0, le=0.01)
    approved_nav_pct: float = Field(ge=0, le=0.01)
    risk_status: Literal["approved", "rejected"]
    human_status: Literal["pending", "approved", "rejected"]
    reason: str
