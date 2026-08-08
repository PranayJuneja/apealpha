from __future__ import annotations

import re

# Legal form, geography and structural words that appear in registered names but
# never in how people actually refer to a company. "Rocket Lab USA, Inc." is
# "Rocket Lab" everywhere a human writes about it.
_NOISE = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "companies",
    "ltd", "limited", "plc", "llc", "lp", "holdings", "holding", "group",
    "international", "usa", "us", "america", "american", "worldwide", "global",
    "technologies", "technology", "systems", "solutions", "industries",
    "enterprises", "ventures", "partners", "trust", "the", "sa", "nv", "ag",
    "class", "common", "stock", "shares", "new", "cl",
}

_SPLIT = re.compile(r"[^A-Za-z0-9&']+")


def company_root(company: str, *, max_words: int = 3) -> str:
    """The part of a registered name people actually say out loud.

    Used for search queries and mention matching. Returns an empty string when
    nothing distinctive survives, so callers can fall back to the symbol rather
    than searching for "Holdings".
    """
    head = company.split(",")[0]
    words = [word for word in _SPLIT.split(head) if word]

    kept: list[str] = []
    for word in words:
        if word.lower() in _NOISE:
            # A noise word only terminates the name once something real precedes
            # it; "The Trade Desk" must not collapse to nothing.
            if kept:
                break
            continue
        kept.append(word)
        if len(kept) >= max_words:
            break

    root = " ".join(kept).strip()
    return root if len(root) >= 3 else ""
