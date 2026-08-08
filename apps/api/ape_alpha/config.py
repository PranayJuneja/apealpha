from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _load_env_file() -> Path | None:
    """Load the nearest .env, walking up from this file to the repo root.

    Real environment variables always win: a shell export or a CI secret should
    never be silently overridden by a checked-out file.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return candidate
    return None


ENV_FILE = _load_env_file()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration.

    Every credential is optional. A missing credential disables exactly one
    source and is reported through source health, so the engine still returns a
    usable answer from whatever remains.
    """

    reddit_client_id: str = field(default_factory=lambda: _env("REDDIT_CLIENT_ID"))
    reddit_client_secret: str = field(default_factory=lambda: _env("REDDIT_CLIENT_SECRET"))
    reddit_user_agent: str = field(
        default_factory=lambda: _env("REDDIT_USER_AGENT", "python:ape-alpha:0.2.0 (research)")
    )
    alpaca_key: str = field(default_factory=lambda: _env("ALPACA_API_KEY"))
    alpaca_secret: str = field(default_factory=lambda: _env("ALPACA_SECRET_KEY"))
    groq_api_key: str = field(default_factory=lambda: _env("GROQ_API_KEY"))
    groq_model: str = field(default_factory=lambda: _env("GROQ_MODEL", "llama-3.3-70b-versatile"))
    sec_user_agent: str = field(
        default_factory=lambda: _env("SEC_USER_AGENT", "APE Alpha research contact@example.com")
    )
    data_dir: Path = field(default_factory=lambda: Path(_env("APE_DATA_DIR", "./data")).resolve())
    cache_ttl_seconds: int = field(default_factory=lambda: int(_env("APE_CACHE_TTL", "300") or 300))
    request_timeout_seconds: float = field(
        default_factory=lambda: float(_env("APE_HTTP_TIMEOUT", "12") or 12)
    )

    @property
    def reddit_enabled(self) -> bool:
        return bool(self.reddit_client_id and self.reddit_client_secret)

    @property
    def alpaca_enabled(self) -> bool:
        return bool(self.alpaca_key and self.alpaca_secret)

    @property
    def groq_enabled(self) -> bool:
        return bool(self.groq_api_key)


_settings: Settings | None = None


def settings() -> Settings:
    """Process-wide settings, read from the environment once."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Drop the cached settings so tests can re-read a patched environment."""
    global _settings
    _settings = None
