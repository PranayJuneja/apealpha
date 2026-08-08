from __future__ import annotations

from ..contracts import NarrativePhase, Playbook, SignalFeatures, SourceStatus

# Hard ceiling on any single paper position, applied before anything else has a
# say. Nothing downstream can raise it.
MAX_NAV_PCT = 0.01


def _social_live(coverage: list[SourceStatus]) -> bool:
    # `reddit` is retained for old stored/test rows; new live runs call the
    # current WebCMD Reddit acquisition leg `social`.
    return any(status.source in {"social", "reddit"} and status.status == "live" for status in coverage)


def _risks(features: SignalFeatures, coverage: list[SourceStatus]) -> list[str]:
    risks: list[str] = []
    dark = [status.source for status in coverage if status.status != "live"]
    if dark:
        risks.append(f"Computed without {', '.join(dark)}. Treat the affected metrics as partial.")

    social_live = _social_live(coverage)
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
    social_dark = not _social_live(coverage)
    risks = _risks(features, coverage)

    if conflict:
        return Playbook(
            stance="STAND_ASIDE",
            rationale="The sources disagree about what is happening. Wait for a clearer picture instead of acting on conflicting information.",
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
                "Investor conversation data is unavailable, so APE Alpha cannot tell whether the crowd is "
                "early or late. The result only reflects news and price; wait for a complete search before "
                "considering a paper position."
            ),
            entry_trigger="Wait until investor conversation data is available. APE Alpha will not size a position it cannot fully measure.",
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
                f"The price moved {features.pre_signal_return:+.1%} before most investors started talking, "
                "and conversation is now slowing. The story looks late, so chasing it carries more risk "
                "than opportunity."
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
                "Investor conversation, news, and price are all unusually active at the same time. The "
                "market already knows the story, so there is no clear early advantage left."
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
                "Investor attention is ahead of news, independent evidence supports the story, and the "
                f"price has moved only {features.pre_signal_return:+.1%} recently. This is the setup APE "
                "Alpha looks for: a real story that may not be fully priced in yet."
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
            blockers.append("investor conversation data is unavailable, so the timing cannot be trusted")
        return Playbook(
            stance="WATCH",
            rationale=(
                "The story has supporting evidence, but it does not yet meet every rule for a paper buy: "
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
            "Investor attention appears early, but no reliable outside source has confirmed the story yet. "
            "Keep watching: this is where both genuine opportunities and false alarms begin."
        ),
        entry_trigger="Wait for a filing, a tier-one story or an IR release to confirm the claim before sizing anything.",
        invalidation="Abandon if attention decays without any confirming evidence appearing within 48 hours.",
        time_stop_hours=48,
        max_nav_pct=0.0,
        expected_holding_period="—",
        risks=risks,
    )
