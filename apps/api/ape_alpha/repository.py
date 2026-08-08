from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_json(name: str) -> dict[str, Any]:
    path = project_root() / "data" / "derived" / name
    if not path.exists():
        raise FileNotFoundError(
            f"{name} has not been produced yet. Populate the store with "
            "`npm run backfill -- <ticker>` and then run `npm run backtest`."
        )
    return json.loads(path.read_text(encoding="utf-8"))
