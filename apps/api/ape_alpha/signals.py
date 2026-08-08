from __future__ import annotations

import math
import statistics
from typing import Iterable

from .contracts import NarrativePhase, SignalFeatures


SIGNAL_VERSION = "narrative-gap-v2"
CLASSIFIER_VERSION = "rules-v2"


# A z-score has no finite value when the baseline has zero dispersion, but the
# event is real and usually the most abnormal thing that can happen. Reporting
# zero there would silently discard exactly the regime breaks this engine exists
# to catch, so a departure from a flat baseline saturates instead.
MAX_Z = 6.0


def robust_zscore(current: float, history: Iterable[float]) -> float:
    """Robust point-in-time z-score using only supplied prior observations."""
    values = [float(value) for value in history]
    if len(values) < 5:
        return 0.0
    median = statistics.median(values)
    deviations = [abs(value - median) for value in values]
    mad = statistics.median(deviations)
    if mad > 1e-9:
        return max(-MAX_Z, min(MAX_Z, (float(current) - median) / (1.4826 * mad)))
    stdev = statistics.pstdev(values)
    if stdev > 1e-9:
        return max(-MAX_Z, min(MAX_Z, (float(current) - median) / stdev))
    difference = float(current) - median
    if abs(difference) <= 1e-9:
        return 0.0
    return MAX_Z if difference > 0 else -MAX_Z


def rolling_robust_zscore(observations: list[float], index: int, lookback: int = 60) -> float:
    """Score an observation against prior values; values at/after index are inaccessible."""
    if index < 0 or index >= len(observations):
        raise IndexError("index is outside observations")
    if lookback < 5:
        raise ValueError("lookback must be at least 5")
    history = observations[max(0, index - lookback):index]
    return robust_zscore(observations[index], history)


def already_pumped_penalty(pre_signal_return: float, market_z: float) -> float:
    return min(1.0, max(0.0, (pre_signal_return - 0.03) / 0.12 + max(0.0, market_z - 2.0) * 0.12))


def classify_phase(features: SignalFeatures) -> NarrativePhase:
    if (
        features.social_z >= 3.0
        and features.already_pumped_penalty >= 0.55
        and features.social_acceleration < 0.7
    ):
        return NarrativePhase.EXIT_LIQUIDITY
    if features.social_z >= 4.0 and features.news_z >= 2.0 and features.market_z >= 2.0:
        return NarrativePhase.MANIA
    if features.social_z >= 2.0 and (features.news_z >= 1.0 or features.filing_confirmed):
        return NarrativePhase.CONFIRMED
    return NarrativePhase.WHISPER


def phase_confidence(features: SignalFeatures, phase: NarrativePhase) -> float:
    # There is no confidence in a phase that was never determined.
    if phase is NarrativePhase.INDETERMINATE:
        return 0.0
    separation = max(abs(features.social_news_gap), abs(features.social_price_gap))
    evidence = 0.12 * min(features.unique_authors, 5) + 0.25 * features.catalyst_quality
    if phase == NarrativePhase.EXIT_LIQUIDITY:
        evidence += 0.35 * features.already_pumped_penalty
    return round(min(0.98, max(0.35, 0.35 + separation * 0.07 + evidence)), 3)


def finite(value: float) -> float:
    return value if math.isfinite(value) else 0.0
