"""Command-line wrapper: PDF path in, JSON contract on stdout.

    python -m pricelistparser.cli LIST.pdf --supplier van_whole --pretty

Exit codes: 0 ok, 2 usage/parse error.
"""

from __future__ import annotations

import argparse
import json
import sys

from .dispatch import UnknownSupplier
from .pipeline import parse_pricelist


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pricelistparser", description=__doc__)
    ap.add_argument("pdf", help="path to the price-list PDF")
    ap.add_argument("--supplier", help="supplier slug; auto-detected when omitted")
    ap.add_argument("--pretty", action="store_true", help="indent the JSON output")
    args = ap.parse_args(argv)

    try:
        result = parse_pricelist(args.pdf, supplier=args.supplier)
    except (UnknownSupplier, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    json.dump(
        result.to_dict(),
        sys.stdout,
        indent=2 if args.pretty else None,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
