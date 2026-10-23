"""The interface every supplier parser implements."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pdfplumber

from ..contract import ParseResult


@runtime_checkable
class SupplierParser(Protocol):
    slug: str  # stable identifier, matches the DB suppliers.slug
    key: str  # parser key recorded on each price_list (usually == slug)
    version: str  # bump when extraction logic changes in a way that alters output

    def sniff(self, pdf: pdfplumber.PDF) -> float:
        """Confidence in [0, 1] that this PDF is this supplier's format."""
        ...

    def parse(
        self, pdf: pdfplumber.PDF, *, sha256: str, source_filename: str | None
    ) -> ParseResult:
        """Extract the raw grid into the supplier-neutral contract."""
        ...
