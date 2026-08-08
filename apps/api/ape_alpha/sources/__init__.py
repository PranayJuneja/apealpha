"""Live acquisition adapters.

Each module owns exactly one upstream contract and normalizes it into plain
dictionaries. None of them decide anything; scoring lives in `research`.
"""

from .http import SourceError, SourceUnavailable

__all__ = ["SourceError", "SourceUnavailable"]
