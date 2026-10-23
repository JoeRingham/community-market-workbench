"""The supplier-neutral JSON contract emitted by every raw-extraction parser.

Keep this stable. The Go side validates and persists against these field names.
Anything supplier-specific (tag meanings, description sub-fields) belongs to
enrichment, not here.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "1"


@dataclass
class Row:
    page: int  # 1-based PDF page number
    column: str  # "left" | "right"
    section: str | None  # running section header, normalized (e.g. "FRUITS")
    description: str  # verbatim row text with the trailing price token removed
    price_raw: str | None  # exact price token as printed ("31.75", "N/A") or None
    price: float | None  # numeric price, None when N/A or missing
    unavailable: bool  # True when the printed price was "N/A"
    price_basis: str  # "case" | "lb" | "each" — structural guess from the row text
    supplier_sku: str | None  # 4+ digit code found in the row, if any
    bbox: list[float]  # [x0, top, x1, bottom] of the row, PDF points
    source_line: str  # full raw row text including the price, for debugging


@dataclass
class Meta:
    supplier: str  # slug, e.g. "van_whole"
    parser_key: str  # which parser ran, e.g. "van_whole"
    parser_version: str  # parser module version
    contract_version: str  # this file's CONTRACT_VERSION
    currency: str  # ISO 4217, e.g. "CAD"
    effective_from: str | None  # ISO date parsed from the list header
    effective_to: str | None  # ISO date
    issued_date: str | None  # ISO date from PDF metadata CreationDate
    page_count: int
    data_pages: list[int]  # pages treated as price tables
    sha256: str
    source_filename: str | None
    row_count: int


@dataclass
class Warning:
    code: str  # machine-readable, e.g. "no_effective_date", "orphan_price"
    detail: str
    page: int | None = None


@dataclass
class ParseResult:
    meta: Meta
    rows: list[Row] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": dataclasses.asdict(self.meta),
            "rows": [dataclasses.asdict(r) for r in self.rows],
            "warnings": [dataclasses.asdict(w) for w in self.warnings],
        }
