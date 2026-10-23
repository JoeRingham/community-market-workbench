"""Map a supplier slug to its parser, or detect the supplier from the PDF."""

from __future__ import annotations

import pdfplumber

from .suppliers.base import SupplierParser
from .suppliers.van_whole import PARSER as VAN_WHOLE

REGISTRY: dict[str, SupplierParser] = {
    VAN_WHOLE.slug: VAN_WHOLE,
}

SNIFF_THRESHOLD = 0.6


class UnknownSupplier(Exception):
    pass


def get_parser(slug: str) -> SupplierParser:
    try:
        return REGISTRY[slug]
    except KeyError as e:
        raise UnknownSupplier(f"no parser registered for supplier {slug!r}") from e


def detect(pdf: pdfplumber.PDF) -> tuple[str | None, float]:
    """Return (slug, confidence) for the best-matching parser, or (None, 0.0)."""
    best_slug, best_score = None, 0.0
    for slug, parser in REGISTRY.items():
        score = parser.sniff(pdf)
        if score > best_score:
            best_slug, best_score = slug, score
    if best_score < SNIFF_THRESHOLD:
        return None, best_score
    return best_slug, best_score
