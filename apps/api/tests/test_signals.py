from __future__ import annotations

from datetime import date

import pytest

from ape_alpha.contracts import NarrativePhase, SignalFeatures
from ape_alpha.research.engine import detect_conflict
from ape_alpha.research.playbook import MAX_NAV_PCT, build_playbook
from ape_alpha.research.resolve import apply_alias
from ape_alpha.signals import (
    MAX_Z,
    already_pumped_penalty,
    classify_phase,
    robust_zscore,
    rolling_robust_zscore,
)
from ape_alpha.contracts import SourceStatus


def features(**overrides) -> SignalFeatures:
    values = dict(
        social_count=45, unique_authors=11, social_acceleration=2.2, social_z=4.1,
        dd_density=0.6, bull_ratio=0.76, news_count=2, news_z=0.5,
        catalyst_quality=0.75, novelty=0.8, filing_confirmed=False,
        market_z=0.6, relative_volume=1.2, abnormal_return_recent=0.004,
        price_resolution="1Day", pre_signal_return=0.01, social_news_gap=3.6,
        social_price_gap=3.5, news_price_gap=-0.1, already_pumped_penalty=0.0,
    )
    values.update(overrides)
    return SignalFeatures(**values)


def live_coverage() -> list[SourceStatus]:
    return [
        SourceStatus(source="social", status="live", provider="webcmd-reddit", events=45),
        SourceStatus(source="news", status="live", provider="gdelt", events=2),
        SourceStatus(source="price", status="live", provider="stooq", events=180),
        SourceStatus(source="filings", status="live", provider="sec-edgar", events=1),
    ]


def test_robust_zscore_uses_only_passed_history() -> None:
    tape = [8, 9, 7, 8, 8, 10, 9, 7, 40, 11, 12, 13]
    original = rolling_robust_zscore(tape, 8)
    tape[9:] = [5000, -5000, 9000]
    assert rolling_robust_zscore(tape, 8) == original


def test_flat_baseline_broken_by_a_spike_saturates_rather_than_scoring_zero() -> None:
    # A perfectly quiet history has no dispersion. Returning 0 here would
    # discard the regime break instead of flagging it.
    assert robust_zscore(10, [1, 1, 1, 1, 1, 1]) == MAX_Z
    assert robust_zscore(-10, [1, 1, 1, 1, 1, 1]) == -MAX_Z
    assert robust_zscore(1, [1, 1, 1, 1, 1, 1]) == 0.0


def test_zscores_are_capped_in_both_directions() -> None:
    assert robust_zscore(10_000, [1, 2, 1, 2, 1, 2]) == MAX_Z
    assert robust_zscore(-10_000, [1, 2, 1, 2, 1, 2]) == -MAX_Z


def test_short_history_refuses_to_score() -> None:
    assert robust_zscore(99, [1, 1]) == 0.0


def test_phase_rules_cover_discovery_mania_and_exit() -> None:
    assert classify_phase(features()) is NarrativePhase.WHISPER
    assert classify_phase(features(news_z=1.5, social_news_gap=2.6)) is NarrativePhase.CONFIRMED
    assert classify_phase(features(news_z=2.4, market_z=2.8)) is NarrativePhase.MANIA
    assert classify_phase(features(social_acceleration=0.4, already_pumped_penalty=0.8)) is NarrativePhase.EXIT_LIQUIDITY


def test_already_pumped_penalty_is_bounded() -> None:
    assert already_pumped_penalty(-0.2, -4) == 0
    assert already_pumped_penalty(1.4, 12) == 1


def test_point_in_time_symbol_rename() -> None:
    assert apply_alias("FB", date(2021, 1, 1)) == "FB"
    assert apply_alias("FB", date(2023, 1, 1)) == "META"
    assert apply_alias("ASTS", date(2026, 1, 1)) == "ASTS"


def test_conflict_forces_stand_aside() -> None:
    plan = build_playbook(features(news_z=1.2), NarrativePhase.CONFIRMED, live_coverage(), conflict=True)
    assert plan.stance == "STAND_ASIDE"
    assert plan.max_nav_pct == 0.0


def test_qualifying_signal_produces_a_capped_paper_long() -> None:
    plan = build_playbook(features(news_z=1.5), NarrativePhase.CONFIRMED, live_coverage())
    assert plan.stance == "PAPER_LONG"
    assert 0 < plan.max_nav_pct <= MAX_NAV_PCT
    assert plan.invalidation and plan.entry_trigger


@pytest.mark.parametrize("status", ["unavailable", "degraded"])
def test_a_social_leg_that_is_not_live_can_never_produce_a_position(status: str) -> None:
    coverage = live_coverage()
    coverage[0] = SourceStatus(source="social", status=status, detail="no usable data")  # type: ignore[arg-type]
    plan = build_playbook(features(news_z=1.5), NarrativePhase.CONFIRMED, coverage)
    assert plan.stance == "WATCH"
    assert plan.max_nav_pct == 0.0
    assert "investor conversation data is unavailable" in plan.rationale.lower()


def test_social_risks_are_suppressed_when_the_social_leg_is_dark() -> None:
    coverage = live_coverage()
    coverage[0] = SourceStatus(source="social", status="unavailable", detail="no authorized session")
    plan = build_playbook(features(unique_authors=0, social_count=0), NarrativePhase.WHISPER, coverage)
    # "0 distinct authors" is an absence of data, not a finding about the crowd.
    assert not any("distinct authors" in risk for risk in plan.risks)
    assert any("Computed without" in risk for risk in plan.risks)


def test_price_risks_are_suppressed_when_the_price_leg_is_dark() -> None:
    coverage = live_coverage()
    coverage[2] = SourceStatus(source="price", status="degraded", detail="HTTP 404")
    plan = build_playbook(features(relative_volume=0.0), NarrativePhase.WHISPER, coverage)
    assert not any("thin liquidity" in risk for risk in plan.risks)


@pytest.mark.parametrize("phase", [NarrativePhase.MANIA, NarrativePhase.EXIT_LIQUIDITY])
def test_late_phases_never_size_a_position(phase: NarrativePhase) -> None:
    plan = build_playbook(features(), phase, live_coverage())
    assert plan.stance == "STAND_ASIDE"
    assert plan.max_nav_pct == 0.0


def test_position_size_shrinks_as_the_move_gets_expensive() -> None:
    cheap = build_playbook(features(news_z=1.5, already_pumped_penalty=0.0), NarrativePhase.CONFIRMED, live_coverage())
    dear = build_playbook(features(news_z=1.5, already_pumped_penalty=0.3), NarrativePhase.CONFIRMED, live_coverage())
    assert dear.max_nav_pct < cheap.max_nav_pct


def test_indeterminate_phase_has_no_confidence_and_no_position() -> None:
    from ape_alpha.signals import phase_confidence

    assert phase_confidence(features(), NarrativePhase.INDETERMINATE) == 0.0
    plan = build_playbook(features(), NarrativePhase.INDETERMINATE, live_coverage())
    assert plan.stance == "WATCH"
    assert plan.max_nav_pct == 0.0
    assert "cannot tell whether the crowd is early or late" in plan.rationale


def test_an_unmeasured_social_leg_is_never_narrated_as_a_quiet_crowd() -> None:
    from ape_alpha.research.llm import rules_narrative

    plan = build_playbook(features(), NarrativePhase.INDETERMINATE, live_coverage())
    text = rules_narrative("ASTS", "AST SpaceMobile", features(social_z=0.0), NarrativePhase.INDETERMINATE, plan)
    assert "did not report" in text
    # The WHISPER phrasing would claim the crowd is ahead of the news, which is
    # the opposite of what a zeroed social block actually means.
    assert "running ahead" not in text


def test_a_slow_source_degrades_that_leg_rather_than_failing_the_run() -> None:
    from ape_alpha.research.engine import _unwrap

    data, status = _unwrap(TimeoutError(), "news", "gdelt")
    assert data is None
    assert status.status == "degraded"
    assert "did not answer" in status.detail


def test_missing_credentials_and_a_failed_fetch_are_different_states() -> None:
    from ape_alpha.research.engine import _unwrap
    from ape_alpha.sources.http import SourceError as Err
    from ape_alpha.sources.http import SourceUnavailable as Missing

    # Only "unavailable" means "never configured"; both block sizing, but the
    # operator needs to know which one to go fix.
    _, absent = _unwrap(Missing("reddit", "no credentials"), "reddit")
    _, failed = _unwrap(Err("reddit", "HTTP 500"), "reddit")
    assert absent.status == "unavailable"
    assert failed.status == "degraded"


def test_conflict_detection_flags_a_split_crowd_and_a_fight_with_the_tape() -> None:
    assert detect_conflict(features(bull_ratio=0.5), posts_scored=20) is True
    assert detect_conflict(features(bull_ratio=0.8, social_z=3.0, market_z=-2.5), posts_scored=20) is True
    assert detect_conflict(features(bull_ratio=0.8, social_z=3.0, market_z=0.4), posts_scored=20) is False
