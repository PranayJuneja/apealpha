"""Live research: resolve a query, score it against real sources, plan a paper trade."""

from .engine import UnresolvedQuery, research
from .resolve import resolve

__all__ = ["UnresolvedQuery", "research", "resolve"]
