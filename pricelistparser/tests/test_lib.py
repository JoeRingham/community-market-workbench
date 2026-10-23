"""Unit tests for the shared helpers. No PDF fixtures — these run everywhere."""

from __future__ import annotations

from pricelistparser.lib import layout, text
from pricelistparser.lib import price as price_lib


def w(t: str, x0: float, x1: float, top: float = 100.0, bottom: float = 110.0) -> dict:
    return {"text": t, "x0": x0, "x1": x1, "top": top, "bottom": bottom}


# --- price -----------------------------------------------------------------


def test_classify_price():
    assert price_lib.classify("31.75") == (True, 31.75, False)
    assert price_lib.classify("479.00") == (True, 479.0, False)
    assert price_lib.classify("1234") == (True, 1234.0, False)


def test_classify_na():
    assert price_lib.classify("N/A") == (True, None, True)
    assert price_lib.classify("na") == (True, None, True)


def test_classify_not_a_price():
    assert price_lib.classify("12.5").is_price is False  # needs two decimals
    assert price_lib.classify("APPLES").is_price is False
    assert price_lib.classify("8X1").is_price is False


# --- text ----------------------------------------------------------------


def test_looks_like_section_header():
    assert text.looks_like_section_header(list("FRUITS"))
    assert text.looks_like_section_header(["S", "A", "L", "A", "D", "-", "M", "A", "N", "N", "S"])
    assert not text.looks_like_section_header(["APPLES", "FUJI", "PREMIUM", "WASH"])
    assert not text.looks_like_section_header(["A", "B"])  # below min_words


def test_reconstruct_spaced_single_word():
    words = [w(c, 10 + i * 8, 16 + i * 8) for i, c in enumerate("FRUITS")]
    assert text.reconstruct_spaced(words) == "FRUITS"


def test_reconstruct_spaced_multi_word():
    # "AB" then a wide gap then "CD"
    words = [w("A", 0, 6), w("B", 8, 14), w("C", 60, 66), w("D", 68, 74)]
    assert text.reconstruct_spaced(words) == "AB CD"


def test_normalize_section():
    assert text.normalize_section("  salad - organic ") == "SALAD - ORGANIC"
    assert text.normalize_section("FRUITS.") == "FRUITS"


def test_find_effective_range_same_month():
    assert text.find_effective_range("VAN-WHOLE  Aug 24 - 26, 2026  PRICE LIST") == (
        "2026-08-24",
        "2026-08-26",
    )


def test_find_effective_range_cross_month():
    assert text.find_effective_range("Aug 30 - Sep 1, 2026") == ("2026-08-30", "2026-09-01")


def test_find_effective_range_none():
    assert text.find_effective_range("no date here") is None


# --- layout ------------------------------------------------------------


def test_cluster_lines_groups_by_baseline():
    words = [w("A", 0, 10, top=100), w("B", 20, 30, top=101), w("C", 0, 10, top=140)]
    lines = layout.cluster_lines(words, y_tol=3.0)
    assert [ln.text for ln in lines] == ["A B", "C"]


def test_split_price_detaches_anchored_token():
    line = layout.Line(
        100, 110, 0, 302, [w("GINGER", 0, 40), w("PERU", 45, 70), w("57.50", 280, 302)]
    )
    sl = layout.split_price(line, anchor_x1=302.2, anchor_tol=14)
    assert sl.description == "GINGER PERU"
    assert (sl.price, sl.price_raw, sl.unavailable) == (57.5, "57.50", False)


def test_split_price_keeps_unanchored_number():
    # a trailing number far from the price column stays in the description
    line = layout.Line(100, 110, 0, 120, [w("PACK", 0, 40), w("100", 90, 110)])
    sl = layout.split_price(line, anchor_x1=302.2, anchor_tol=14)
    assert sl.description == "PACK 100"
    assert sl.price_raw is None


def test_merge_orphan_prices():
    rows = [
        layout.SplitLine("LONG DESC (E.B.) 4510097", None, None, False, [], 200, 208, 0, 240),
        layout.SplitLine("", "29.75", 29.75, False, [], 210, 218, 250, 262),
    ]
    merged = layout.merge_orphan_prices(rows, max_gap=6.0)
    assert len(merged) == 1
    assert merged[0].description == "LONG DESC (E.B.) 4510097"
    assert merged[0].price == 29.75
