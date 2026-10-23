"""pricelistparser — raw extraction of supplier price-list files into a supplier-neutral JSON contract.

Public entry points:
    pricelistparser.parse_pricelist(path, supplier=None) -> ParseResult
    pricelistparser.cli                                  -> command-line wrapper
"""

from .contract import Meta, ParseResult, Row, Warning
from .pipeline import parse_pricelist

__all__ = ["Meta", "ParseResult", "Row", "Warning", "parse_pricelist"]
