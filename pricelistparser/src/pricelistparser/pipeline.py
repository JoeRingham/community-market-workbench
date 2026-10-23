"""Open a price-list file, pick a parser, run raw extraction."""

from __future__ import annotations

import hashlib
import os

import pdfplumber

from . import dispatch
from .contract import ParseResult, Warning


def parse_pricelist(path: str, *, supplier: str | None = None) -> ParseResult:
    """Parse `path` with the named supplier parser, or auto-detect when omitted."""
    with open(path, "rb") as fh:
        data = fh.read()
    sha256 = hashlib.sha256(data).hexdigest()
    filename = os.path.basename(path)

    with pdfplumber.open(path) as pdf:
        if supplier:
            parser = dispatch.get_parser(supplier)
            confidence = parser.sniff(pdf)
        else:
            slug, confidence = dispatch.detect(pdf)
            if slug is None:
                raise dispatch.UnknownSupplier(
                    f"could not identify supplier (best confidence {confidence:.2f})"
                )
            parser = dispatch.get_parser(slug)

        result = parser.parse(pdf, sha256=sha256, source_filename=filename)

    if confidence < dispatch.SNIFF_THRESHOLD:
        result.warnings.insert(
            0,
            Warning(
                "low_sniff_confidence",
                f"{parser.key} sniff confidence {confidence:.2f} for a list parsed as {parser.key}",
            ),
        )
    return result
