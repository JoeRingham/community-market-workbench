"""Geometry helpers: cluster words into rows, split columns, detach prices."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import price as price_lib


@dataclass
class Line:
    """A visually-aligned run of words within one column."""

    top: float
    bottom: float
    x0: float
    x1: float
    words: list[dict] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w["text"] for w in sorted(self.words, key=lambda w: w["x0"]))


def cluster_lines(words: list[dict], *, y_tol: float = 3.0) -> list[Line]:
    """Group words whose baselines are within `y_tol` points into Lines, top→bottom."""
    ws = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
    lines: list[Line] = []
    for w in ws:
        placed = False
        for ln in lines:
            if abs(w["top"] - ln.top) <= y_tol:
                ln.words.append(w)
                ln.top = min(ln.top, w["top"])
                ln.bottom = max(ln.bottom, w["bottom"])
                ln.x0 = min(ln.x0, w["x0"])
                ln.x1 = max(ln.x1, w["x1"])
                placed = True
                break
        if not placed:
            lines.append(Line(w["top"], w["bottom"], w["x0"], w["x1"], [w]))
    lines.sort(key=lambda ln: ln.top)
    return lines


def in_box(words: list[dict], *, x_lo: float, x_hi: float, y_lo: float, y_hi: float) -> list[dict]:
    return [w for w in words if x_lo <= w["x0"] < x_hi and y_lo <= w["top"] <= y_hi]


@dataclass
class SplitLine:
    description: str
    price_raw: str | None
    price: float | None
    unavailable: bool
    words: list[dict]
    top: float
    bottom: float
    x0: float
    x1: float


def split_price(line: Line, *, anchor_x1: float, anchor_tol: float = 14.0) -> SplitLine:
    """Detach a right-aligned price token whose right edge sits near `anchor_x1`."""
    ws = sorted(line.words, key=lambda w: w["x0"])
    price_raw = price_val = None
    unavailable = False
    desc_words = ws
    if ws:
        last = ws[-1]
        pt = price_lib.classify(last["text"])
        if pt.is_price and abs(last["x1"] - anchor_x1) <= anchor_tol:
            price_raw = last["text"]
            price_val = pt.value
            unavailable = pt.unavailable
            desc_words = ws[:-1]
    description = " ".join(w["text"] for w in desc_words).strip()
    return SplitLine(
        description=description,
        price_raw=price_raw,
        price=price_val,
        unavailable=unavailable,
        words=desc_words,
        top=line.top,
        bottom=line.bottom,
        x0=line.x0,
        x1=line.x1,
    )


def merge_orphan_prices(rows: list[SplitLine], *, max_gap: float = 6.0) -> list[SplitLine]:
    """Fix rows where a long description pushed its price onto a sub-line.

    Pattern: a price-only line sitting a few points below a description-only line.
    Merge the price up into the description row.
    """
    out: list[SplitLine] = []
    skip = set()
    for i, row in enumerate(rows):
        if i in skip:
            continue
        is_price_only = row.price_raw is not None and not row.description
        prev = out[-1] if out else None
        if (
            is_price_only
            and prev is not None
            and prev.price_raw is None
            and prev.description
            and abs(row.top - prev.bottom) <= max_gap
        ):
            prev.price_raw = row.price_raw
            prev.price = row.price
            prev.unavailable = row.unavailable
            prev.bottom = max(prev.bottom, row.bottom)
            prev.x1 = max(prev.x1, row.x1)
            continue
        out.append(row)
    return out
