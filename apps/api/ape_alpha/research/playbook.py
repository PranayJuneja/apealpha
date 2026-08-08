from __future__ import annotations

from ..contracts import NarrativePhase, Playbook, SignalFeatures, SourceStatus

# Hard ceiling on any single paper position, applied before anything else has a
# say. Nothing downstream can raise it.
MAX_NAV_PCT = 0.01


def _risks(features: SignalFeatures, coverage: list[SourceStatus]) -> list[str]:
    risks: list[str] = []
    dark = [status.source for status in coverage if status.status != "live"]
    if dark:
        risks.append(f"Computed without {', '.join(dark)}. Treat the affected metrics as partial.")

    social_live = any(status.source == "reddit" and status.status == "live" for status in coverage)
    price_live = any(status.source == "price" and status.status == "live" for status in coverage)

    if price_live and features.already_pumped_penalty >= 0.4:
        risks.append(
            f"The security had already moved {features.pre_signal_return:+.1%} over the prior five bars. "
            "Entry here pays for a move that has happened."
        )
    # Social-derived warnings are only meaningful when the social leg answered.
    # Reporting "0 distinct authors" for a dark source reads as a finding rather
    # than an absence of data.
    if social_live and features.unique_authors < 5:
        risks.append(
            f"Only {features.unique_authors} distinct authors. This is thin enough to be one person "
            "posting repeatedly, or coordinated."
        )
    if social_live and features.bull_ratio >= 0.9:
        risks.append("Bullish agreement above 90% historically marks crowding, not conviction.")
    if social_live and features.dd_density < 0.2 and features.social_count >= 8:
        risks.append("Volume without argument: almost none of the discussion carries analysis.")
    if features.novelty < 0.35 and features.news_count > 0:
        risks.append("Most recent coverage is syndicated repetition of one story, not new information.")
    if price_live and features.relative_volume < 0.8:
        risks.append("Volume is below its own recent median, so any move rests on thin liquidity.")
    if price_live and features.price_resolution != "1Hour":
        risks.append("Price features are end-of-day. Intraday timing is not represented.")
    return risks


def build_playbook(
    features: SignalFeatures,
    phase: NarrativePhase,
    coverage: list[SourceStatus],
    *,
    conflict: bool = False,
) -> Playbook:
    """Translate a signal into an explicit, checkable paper-trade plan.

    This is a research plan, not advice: every branch states what would have to
    be true to act, what would prove the thesis wrong, and when to stop waiting.
    """
    # Anything other than a live social leg blocks sizing. A degraded fetch is
    # no more trustworthy than a missing credential when the whole thesis rests
    # on measuring social lead.
    social_dark = not any(status.source == "reddit" and status.status == "live" for status in coverage)
    risks = _risks(features, coverage)

    if conflict:
        return Playbook(
            stance="STAND_ASIDE",
            rationale="Sources disagree about what is happening. A signal built on contradictory inputs is not a signal.",
            entry_trigger="None. Re-run once the sources agree.",
            invalidation="Not applicable — no position is contemplated.",
            time_stop_hours=0,
            max_nav_pct=0.0,
            expected_holding_period="—",
            risks=risks,
        )

    if phase is NarrativePhase.INDETERMINATE:
        return Playbook(
            stance="WATCH",
            rationale=(
                "The social leg is dark, so the narrative gap cannot be measured. What is shown below is "
                "news and price only: a zero social score here means unmeasured, not quiet. Connect Reddit "
                "credentials to get a phase at all."
            ),
            entry_trigger="None until the social leg reports. The engine will not size a position it cannot measure.",
            invalidation="Not applicable — no position is contemplated.",
            time_stop_hours=0,
            max_nav_pct=0.0,
            expected_holding_period="—",
            risks=risks,
        )

    if phase is NarrativePhase.EXIT_LIQUIDITY:
        return Playbook(
            stance="STAND_ASIDE",
            rationale=(
                f"Attention arrived after the move. The security ran {features.pre_signal_return:+.1%} before "
                f"the crowd showed up and mention growth is now decelerating ({features.social_acceleration:.2f}×). "
                "Buying here supplies the exit."
            ),
            entry_trigger="None on the long side at this phase.",
            invalidation="Not applicable — no position is contemplated.",
            time_stop_hours=0,
            max_nav_pct=0.0,
            expected_holding_period="—",
            risks=risks,
        )

    if phase is NarrativePhase.MANIA:
        return Playbook(
            stance="STAND_ASIDE",
            rationale=(
                f"Social ({features.social_z:+.1f}σ), news ({features.news_z:+.1f}σ) and price "
                f"({features.market_z:+.1f}σ) are all elevated together. When every layer knows, there is no "
                "informational edge left to harvest."
            ),
            entry_trigger="None. Revisit only if attention decays while the catalyst stays intact.",
            invalidation="Not applicable — no position is contemplated.",
            time_stop_hours=0,
            max_nav_pct=0.0,
            expected_holding_period="—",
            risks=risks,
        )

    qualifies = (
        phase is NarrativePhase.CONFIRMED
        and features.social_news_gap >= 1.5
        and features.already_pumped_penalty < 0.35
        and features.unique_authors >= 5
        and not social_dark
    )

    if qualifies:
        # Size scales down as the story gets more expensive and less evidenced,
        # and never exceeds the hard cap.
        quality = min(1.0, 0.5 + features.catalyst_quality * 0.5)
        crowding = 1.0 - features.already_pumped_penalty
        size = round(min(MAX_NAV_PCT, MAX_NAV_PCT * quality * crowding), 5)
        return Playbook(
            stance="PAPER_LONG",
            rationale=(
                f"Social attention leads news by {features.social_news_gap:+.1f}σ with a catalyst quality of "
                f"{features.catalyst_quality:.0%}, and price has not yet absorbed it "
                f"({features.market_z:+.1f}σ, {features.pre_signal_return:+.1%} trailing). This is the shape "
                "the engine is built to find: the story is real and not yet paid for."
            ),
            entry_trigger=(
                "Enter on the next session open only if the narrative gap is still ≥1.0σ at that point and "
                "no contradicting filing has landed."
            ),
            invalidation=(
                f"Exit if the gap closes below 0σ, if the already-priced penalty rises above 0.5, or if price "
                f"falls more than 8% from entry. Any of the three ends the thesis."
            ),
            time_stop_hours=72,
            max_nav_pct=size,
            expected_holding_period="1–3 sessions",
            risks=risks,
        )

    if phase is NarrativePhase.CONFIRMED:
        blockers = []
        if features.social_news_gap < 1.5:
            blockers.append(f"gap is only {features.social_news_gap:+.1f}σ against a 1.5σ threshold")
        if features.already_pumped_penalty >= 0.35:
            blockers.append(f"already-priced penalty is {features.already_pumped_penalty:.2f}")
        if features.unique_authors < 5:
            blockers.append(f"only {features.unique_authors} distinct authors")
        if social_dark:
            blockers.append("the social leg is dark, so the gap cannot be trusted")
        return Playbook(
            stance="WATCH",
            rationale=(
                "The narrative is confirmed but does not clear the entry bar: "
                + "; ".join(blockers)
                + "."
            ),
            entry_trigger="Re-runs qualify once the gap clears 1.5σ with the penalty under 0.35 and five or more authors.",
            invalidation="Drop it if news catches up to social before price stays flat — the edge will have gone.",
            time_stop_hours=48,
            max_nav_pct=0.0,
            expected_holding_period="—",
            risks=risks,
        )

    return Playbook(
        stance="WATCH",
        rationale=(
            f"Early and unconfirmed. Social is at {features.social_z:+.1f}σ with no independent corroboration "
            "yet, which is where the best entries and the worst false positives both live."
        ),
        entry_trigger="Wait for a filing, a tier-one story or an IR release to confirm the claim before sizing anything.",
        invalidation="Abandon if attention decays without any confirming evidence appearing within 48 hours.",
        time_stop_hours=48,
        max_nav_pct=0.0,
        expected_holding_period="—",
        risks=risks,
    )
