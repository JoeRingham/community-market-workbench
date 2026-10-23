"""Price-token detection and parsing."""

from __future__ import annotations

import re
from typing import NamedTuple

_PRICE_RE = re.compile(r"^\$?(\d{1,4}(?:\.\d{2})?)$")
_NA_RE = re.compile(r"^N/?A$", re.IGNORECASE)


class PriceToken(NamedTuple):
    is_price: bool  # token looks like a price OR an explicit N/A
    value: float | None  # numeric value, None for N/A
    unavailable: bool  # True for N/A


def classify(token: str) -> PriceToken:
    t = token.strip()
    if _NA_RE.match(t):
        return PriceToken(True, None, True)
    m = _PRICE_RE.match(t)
    if m:
        return PriceToken(True, float(m.group(1)), False)
    return PriceToken(False, None, False)
