from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq

from .contracts import ResearchResult, SignalFeatures

SNAPSHOT_FILE = "signal_snapshots.parquet"
MANIFEST_FILE = "manifest.json"

FEATURE_COLUMNS = tuple(SignalFeatures.model_fields.keys())

COLUMNS = (
    "snapshot_id", "ticker", "market", "company", "as_of", "origin", "phase", "action",
    "conflict", "confidence", "social_coverage", "news_coverage", "price_coverage",
    "filing_coverage", "price_provider", "signal_version", "dataset_version",
    *FEATURE_COLUMNS,
)


def derived_dir(root: Path) -> Path:
    path = root / "data" / "derived"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _row(
    *,
    snapshot_id: str,
    ticker: str,
    market: str,
    company: str,
    as_of: datetime,
    origin: str,
    phase: str,
    action: str,
    conflict: bool,
    confidence: float,
    coverage: dict[str, str],
    price_provider: str,
    signal_version: str,
    dataset_version: str,
    features: SignalFeatures,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "ticker": ticker,
        "market": market,
        "company": company,
        "as_of": as_of.astimezone(UTC).isoformat(),
        "origin": origin,
        "phase": phase,
        "action": action,
        "conflict": conflict,
        "confidence": float(confidence),
        "social_coverage": coverage.get("reddit", "unavailable"),
        "news_coverage": coverage.get("news", "unavailable"),
        "price_coverage": coverage.get("price", "unavailable"),
        "filing_coverage": coverage.get("filings", "unavailable"),
        "price_provider": price_provider,
        "signal_version": signal_version,
        "dataset_version": dataset_version,
    }
    row.update(features.model_dump())
    return row


def row_from_result(result: ResearchResult) -> dict[str, Any]:
    """Flatten a live research run into one immutable observation."""
    coverage = {status.source: status.status for status in result.coverage}
    provider = next((status.provider for status in result.coverage if status.source == "price"), "")
    return _row(
        snapshot_id=result.snapshot.snapshot_id,
        ticker=result.ticker,
        market=result.market,
        company=result.company,
        as_of=result.generated_at,
        origin="live",
        phase=result.snapshot.phase.value,
        action=result.snapshot.action,
        conflict=result.snapshot.conflict,
        confidence=result.snapshot.confidence,
        coverage=coverage,
        price_provider=provider,
        signal_version=result.snapshot.signal_version,
        dataset_version=result.snapshot.dataset_version,
        features=result.snapshot.features,
    )


def backfill_row(
    *,
    ticker: str,
    market: str,
    company: str,
    as_of: datetime,
    features: SignalFeatures,
    phase: str,
    price_provider: str,
    signal_version: str,
    dataset_version: str,
    news_measured: bool,
) -> dict[str, Any]:
    """A historical observation reconstructed from real price, and news if available.

    Marked `origin="backfill"` with `social_coverage="unavailable"` so nothing
    downstream can mistake it for a run that saw the social leg. When no news
    baseline exists for the day, the news leg is recorded as unavailable rather
    than the row being dropped — a price-only observation is still evaluable by
    price-only rules, and dropping it would silently shrink the sample.
    """
    return _row(
        snapshot_id=f"bf_{ticker}_{as_of.date().isoformat()}",
        ticker=ticker,
        market=market,
        company=company,
        as_of=as_of,
        origin="backfill",
        phase=phase,
        action="WATCH",
        conflict=False,
        confidence=0.0,
        coverage={
            "reddit": "unavailable",
            "news": "live" if news_measured else "unavailable",
            "price": "live",
            "filings": "unavailable",
        },
        price_provider=price_provider,
        signal_version=signal_version,
        dataset_version=dataset_version,
        features=features,
    )


class StoreSchemaError(RuntimeError):
    """The file on disk was written by an incompatible version of the store."""


def read_snapshots(root: Path) -> list[dict[str, Any]]:
    """Every observation recorded so far, oldest first."""
    path = derived_dir(root) / SNAPSHOT_FILE
    if not path.exists():
        return []

    table = pq.read_table(path)
    missing = [column for column in ("snapshot_id", "as_of", "ticker", "origin") if column not in table.column_names]
    if missing:
        # Failing here with the path named beats a KeyError three frames deep
        # when an older store is left in place across an upgrade.
        raise StoreSchemaError(
            f"{path} is missing {', '.join(missing)}. It was written by an older schema; "
            "delete it or migrate it before appending new observations."
        )
    rows = table.to_pylist()
    # Compatibility repair for snapshots written before INDETERMINATE existed.
    # A dark social leg can never support a social lead/lag phase, regardless
    # of what an older classifier wrote into the row.
    for row in rows:
        if row.get("social_coverage") != "live":
            row["phase"] = "INDETERMINATE"
            row["action"] = "WATCH"
            row["conflict"] = False
            row["confidence"] = 0.0
    return sorted(rows, key=lambda item: (item["as_of"], item["ticker"]))


def append_snapshots(root: Path, rows: Iterable[dict[str, Any]]) -> int:
    """Append observations, de-duplicated on snapshot_id.

    The store is append-only on purpose: a point-in-time record that can be
    rewritten is not a point-in-time record.
    """
    new_rows = [row for row in rows if row]
    if not new_rows:
        return 0

    existing = read_snapshots(root)
    seen = {row["snapshot_id"] for row in existing}
    merged = list(existing)
    added = 0
    for row in new_rows:
        if row["snapshot_id"] in seen:
            continue
        seen.add(row["snapshot_id"])
        merged.append({column: row.get(column) for column in COLUMNS})
        added += 1
    if not added:
        return 0

    # Apply the same compatibility rule before every write so adding any new
    # observation permanently repairs an older on-disk store as well.
    for row in merged:
        if row.get("social_coverage") != "live":
            row["phase"] = "INDETERMINATE"
            row["action"] = "WATCH"
            row["conflict"] = False
            row["confidence"] = 0.0
    merged.sort(key=lambda item: (item["as_of"], item["ticker"]))
    pq.write_table(pa.Table.from_pylist(merged), derived_dir(root) / SNAPSHOT_FILE, compression="zstd")
    write_manifest(root, merged)
    return added


def write_manifest(root: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe what the store actually holds, per source."""
    live = [row for row in rows if row["origin"] == "live"]
    backfill = [row for row in rows if row["origin"] == "backfill"]
    social = [row for row in rows if row.get("social_coverage") == "live"]
    manifest = {
        "datasetVersion": "live-acquisition-v2",
        "datasetLabel": "LIVE ACQUISITION — POINT-IN-TIME STORE",
        "generatedAt": datetime.now(UTC).isoformat(),
        "rows": len(rows),
        "tickers": sorted({row["ticker"] for row in rows}),
        "liveObservations": len(live),
        "backfillObservations": len(backfill),
        "socialObservations": len(social),
        "firstObservation": rows[0]["as_of"] if rows else None,
        "lastObservation": rows[-1]["as_of"] if rows else None,
        "caveats": [
            "News and price legs are backfilled from real historical sources.",
            "The social leg accrues forward only: Reddit publishes no licensed deep history.",
            "Any metric derived from the social leg is unavailable for backfilled rows.",
        ],
    }
    (derived_dir(root) / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def read_manifest(root: Path) -> dict[str, Any]:
    path = derived_dir(root) / MANIFEST_FILE
    if not path.exists():
        return write_manifest(root, read_snapshots(root))
    return json.loads(path.read_text(encoding="utf-8"))
