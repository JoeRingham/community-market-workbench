"""Raw-extraction parser for Van-Whole Produce (Vancouver, BC) weekly price lists.

Format notes (see docs/plan.md):
  * US Legal pages, 612 x 1008 pt.
  * Page 1 is a decorative "New / Seasonal Items" cover (Calibri, photos) - skipped.
  * Data pages are a two-column grid. Reading order is left column top->bottom,
    then right column top->bottom, with the section header carrying across.
  * Prices are right-aligned: right edge ~x302 (left column), ~x590 (right column).
  * Section headers are letter-spaced bold caps ("F R U I T S").
  * Effective date range sits in the header ("Aug 24 - 26, 2026").
"""

from __future__ import annotations

import re

import pdfplumber

from ..contract import CONTRACT_VERSION, Meta, ParseResult, Row, Warning
from ..lib import layout, text
from ..lib import price as price_lib

# --- Layout constants -------------------------------------------------------
PAGE_W, PAGE_H = 612.0, 1008.0
COLUMN_SPLIT_X = 306.0
LEFT_PRICE_X1 = 302.2
RIGHT_PRICE_X1 = 590.4
PRICE_ANCHOR_TOL = 15.0
FOOTER_Y_MIN = 940.0
MIN_PRICE_WORDS_FOR_DATA_PAGE = 5

# Van-Whole uses a small, fixed set of section headers. Letter-spaced text makes
# word boundaries ambiguous ("ROOT CROP" vs "ROOTCROP"), so we snap the
# reconstructed label to this list by its alphanumerics. Unknown labels pass
# through verbatim and raise a warning.
CANONICAL_SECTIONS = [
    "FRUITS",
    "VEGETABLES",
    "HERB",
    "TOFU PRODUCTS",
    "CHINESE ROOT CROP",
    "CHINESE VEGETABLES",
    "EXOTIC FRUITS",
    "ETHNIC EGGPLANTS & MISC",
    "DATES",
    "GROCERY ITEMS",
    "PACKING ITEMS",
    "PRE-CUT FRUIT, VEGGIES & PASTA",
    "SALAD - ORGANIC",
    "SALAD - CONVENTIONAL",
    "SALAD - APIO",
    "SALAD - FRESH EXPRESS",
    "SALAD - MANNS",
    "SALAD - TAYLOR FARM",
    "SALAD - UP VERTICAL FARMS",
]
_CANON_INDEX = {re.sub(r"[^A-Z0-9]", "", s): s for s in CANONICAL_SECTIONS}

FURNITURE_RE = re.compile(
    r"^(VAN-WHOLE PRODUCE|830 MALKIN|TEL:|FAX:|PRICE SUBJECT TO CHANGE|ORGANIC FRUITS AND)",
    re.IGNORECASE,
)
ORGANIC_BANNER_RE = re.compile(r"^ORGANIC FRUITS AND", re.IGNORECASE)
PAGENUM_RE = re.compile(r"^\d{1,3}$")
SKU_RE = re.compile(r"(?<!\d)(\d{4,})(?!\d)")
CREATION_DATE_RE = re.compile(r"D:(\d{4})(\d{2})(\d{2})")


def _guess_basis(desc: str) -> str:
    u = f" {desc.upper()} "
    if "PER LB" in u or "/LB" in u:
        return "lb"
    if " EA " in u or u.rstrip().endswith(" EACH") or "PER EACH" in u:
        return "each"
    return "case"


def _median_x(line: layout.Line) -> float:
    xs = sorted((w["x0"] + w["x1"]) / 2 for w in line.words)
    return xs[len(xs) // 2] if xs else 0.0


def _is_header(words: list) -> bool:
    return bool(words) and text.looks_like_section_header([w["text"] for w in words])


def _snap_section(raw: str) -> tuple[str, bool]:
    key = re.sub(r"[^A-Z0-9]", "", raw.upper())
    if key in _CANON_INDEX:
        return _CANON_INDEX[key], True
    return raw, False


class VanWholeParser:
    slug = "van_whole"
    key = "van_whole"
    version = "0.1.0"

    # -- detection ---------------------------------------------------------
    def sniff(self, pdf: pdfplumber.PDF) -> float:
        probe = " ".join((p.extract_text() or "") for p in pdf.pages[:3]).upper()
        score = 0.0
        if "VAN-WHOLE PRODUCE" in probe:
            score += 0.6
        if "MALKIN AVENUE" in probe:
            score += 0.3
        if pdf.pages and abs(pdf.pages[0].width - PAGE_W) < 2:
            score += 0.1
        return min(score, 1.0)

    # -- main ------------------------------------------------------------
    def parse(
        self, pdf: pdfplumber.PDF, *, sha256: str, source_filename: str | None
    ) -> ParseResult:
        warnings: list[Warning] = []
        rows: list[Row] = []
        data_pages: list[int] = []

        issued = self._issued_date(pdf)
        eff = self._effective_range(pdf)
        if eff is None:
            warnings.append(
                Warning("no_effective_date", "could not parse a date range from the header")
            )

        running_section: str | None = None
        rows_before_section = 0
        unknown_sections: set[str] = set()

        def make_header(raw: str) -> str:
            name, known = _snap_section(text.normalize_section(raw))
            if not known:
                unknown_sections.add(name)
            return name

        for pageno, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            price_words = sum(1 for w in words if price_lib.classify(w["text"]).is_price)
            if price_words < MIN_PRICE_WORDS_FOR_DATA_PAGE:
                continue  # cover / non-tabular page
            data_pages.append(pageno)
            if abs(page.width - PAGE_W) > 2 or abs(page.height - PAGE_H) > 2:
                warnings.append(
                    Warning("unexpected_page_size", f"{page.width:.0f}x{page.height:.0f}", pageno)
                )

            page_lines = layout.cluster_lines(words, y_tol=3.0)
            page_is_organic = False
            events: dict[str, list[tuple[float, str, object]]] = {"left": [], "right": []}

            for ln in page_lines:
                t = ln.text.strip()
                if not t:
                    continue
                if ORGANIC_BANNER_RE.match(t):
                    page_is_organic = True
                    continue
                if FURNITURE_RE.match(t):
                    continue
                if PAGENUM_RE.match(t) and ln.top > FOOTER_Y_MIN:
                    continue
                if text.DATE_RANGE_RE.search(t):
                    continue

                left_ws = [w for w in ln.words if w["x0"] < COLUMN_SPLIT_X]
                right_ws = [w for w in ln.words if w["x0"] >= COLUMN_SPLIT_X]

                # A section header that spans the column gutter (letters run
                # continuously across x306) must not be split into two.
                if _is_header(left_ws) and _is_header(right_ws):
                    gutter = min(w["x0"] for w in right_ws) - max(w["x1"] for w in left_ws)
                    if gutter < 40:
                        name = make_header(text.reconstruct_spaced(ln.words))
                        side = "left" if _median_x(ln) < COLUMN_SPLIT_X else "right"
                        events[side].append((ln.top, "header", name))
                        continue

                for side, ws, anchor in (
                    ("left", left_ws, LEFT_PRICE_X1),
                    ("right", right_ws, RIGHT_PRICE_X1),
                ):
                    if not ws:
                        continue
                    top = min(w["top"] for w in ws)
                    if _is_header(ws):
                        name = make_header(text.reconstruct_spaced(ws))
                        if name:
                            events[side].append((top, "header", name))
                        continue
                    sub = layout.Line(
                        top=top,
                        bottom=max(w["bottom"] for w in ws),
                        x0=min(w["x0"] for w in ws),
                        x1=max(w["x1"] for w in ws),
                        words=ws,
                    )
                    events[side].append(
                        (
                            sub.top,
                            "data",
                            layout.split_price(sub, anchor_x1=anchor, anchor_tol=PRICE_ANCHOR_TOL),
                        )
                    )

            for side in ("left", "right"):
                merged = _merge_within_events(events[side])
                for top, kind, payload in merged:
                    if kind == "header":
                        running_section = payload  # type: ignore[assignment]
                        continue
                    sl: layout.SplitLine = payload  # type: ignore[assignment]
                    if not sl.description and sl.price_raw is None:
                        continue
                    if sl.price_raw is None and not sl.description:
                        continue
                    if running_section is None:
                        rows_before_section += 1
                    if sl.price_raw is None:
                        warnings.append(Warning("row_without_price", sl.description[:80], pageno))
                    sku_m = SKU_RE.search(sl.description)
                    section = running_section
                    if page_is_organic and section and not section.startswith("ORGANIC"):
                        section = f"ORGANIC - {section}"
                    rows.append(
                        Row(
                            page=pageno,
                            column=side,
                            section=section,
                            description=sl.description,
                            price_raw=sl.price_raw,
                            price=sl.price,
                            unavailable=sl.unavailable,
                            price_basis=_guess_basis(sl.description),
                            supplier_sku=sku_m.group(1) if sku_m else None,
                            bbox=[
                                round(sl.x0, 1),
                                round(sl.top, 1),
                                round(sl.x1, 1),
                                round(sl.bottom, 1),
                            ],
                            source_line=(
                                sl.description + (f" {sl.price_raw}" if sl.price_raw else "")
                            ).strip(),
                        )
                    )

        if rows_before_section:
            warnings.append(
                Warning("rows_before_first_section", f"{rows_before_section} row(s) had no section")
            )
        for name in sorted(unknown_sections):
            warnings.append(Warning("unknown_section", name))

        meta = Meta(
            supplier=self.slug,
            parser_key=self.key,
            parser_version=self.version,
            contract_version=CONTRACT_VERSION,
            currency="CAD",
            effective_from=eff[0] if eff else None,
            effective_to=eff[1] if eff else None,
            issued_date=issued,
            page_count=len(pdf.pages),
            data_pages=data_pages,
            sha256=sha256,
            source_filename=source_filename,
            row_count=len(rows),
        )
        return ParseResult(meta=meta, rows=rows, warnings=warnings)

    # -- helpers -------------------------------------------------------
    def _issued_date(self, pdf: pdfplumber.PDF) -> str | None:
        raw = (pdf.metadata or {}).get("CreationDate", "") or ""
        m = CREATION_DATE_RE.search(raw)
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None

    def _effective_range(self, pdf: pdfplumber.PDF) -> tuple[str, str] | None:
        for page in pdf.pages[:4]:
            hit = text.find_effective_range(page.extract_text() or "")
            if hit:
                return hit
        return None


def _merge_within_events(
    events: list[tuple[float, str, object]],
) -> list[tuple[float, str, object]]:
    """Run orphan-price merging over the data items, keeping headers in place."""
    events = sorted(events, key=lambda e: e[0])
    data = [(i, e[2]) for i, e in enumerate(events) if e[1] == "data"]
    merged = layout.merge_orphan_prices([sl for _, sl in data])  # type: ignore[misc]
    # Rebuild: drop data events, re-insert merged splitlines by their top.
    kept = [e for e in events if e[1] == "header"]
    for sl in merged:
        kept.append((sl.top, "data", sl))
    kept.sort(key=lambda e: e[0])
    return kept


PARSER = VanWholeParser()
