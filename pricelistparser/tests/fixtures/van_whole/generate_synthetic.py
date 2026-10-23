"""Build a synthetic, safe-to-publish stand-in for a Van-Whole price list.

Same page size, column geometry, letterhead strings, and letter-spaced section
headers as the real format (so it exercises pricelistparser.suppliers.van_whole
exactly as shipped), but every product, price, and code is fabricated. No real
supplier pricing or product data appears here or in the generated PDF.

Regenerate after a deliberate format/geometry change:

    cd pricelistparser
    uv run python tests/fixtures/van_whole/generate_synthetic.py
    uv run pricelistparser tests/fixtures/van_whole/synthetic.pdf \
        --supplier van_whole --pretty > tests/fixtures/van_whole/synthetic.expected.json
"""

from __future__ import annotations

import io
import pathlib

from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = 612.0, 1008.0
LEFT_X = 74.0
RIGHT_X = 320.0
LEFT_PRICE_X1 = 302.2
RIGHT_PRICE_X1 = 590.4


def y_of(top: float, size: float = 10.0) -> float:
    """Convert a target pdfplumber 'top' (distance from page top) to a reportlab baseline y."""
    return PAGE_H - top - 0.793 * size


class Sheet:
    def __init__(self) -> None:
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=(PAGE_W, PAGE_H))

    def text(
        self, x: float, top: float, s: str, *, font: str = "Helvetica", size: float = 10.0
    ) -> None:
        self.c.setFont(font, size)
        self.c.drawString(x, y_of(top, size), s)

    def price(self, anchor_x1: float, top: float, s: str, *, size: float = 10.0) -> None:
        self.c.setFont("Helvetica", size)
        self.c.drawRightString(anchor_x1, y_of(top, size), s)

    def header(
        self,
        x: float,
        top: float,
        s: str,
        *,
        size: float = 10.0,
        letter_adv: float = 11.0,
        word_gap: float = 30.0,
    ) -> None:
        """Draw a letter-spaced section header, one glyph per pdfplumber 'word'."""
        self.c.setFont("Helvetica-Bold", size)
        cx = x
        for ch in s:
            if ch == " ":
                cx += word_gap
                continue
            self.c.drawString(cx, y_of(top, size), ch)
            cx += letter_adv

    def new_page(self) -> None:
        self.c.showPage()


def build() -> bytes:
    sheet = Sheet()
    c = sheet.c

    # --- Page 1: decorative cover, no prices -> raw extraction skips it as non-data.
    sheet.text(160, 120, "New / Seasonal Items", font="Helvetica-Bold", size=16)
    sheet.text(100, 300, "Sample Item (In Stock)")
    sheet.text(100, 320, "Another Item (In Stock)")
    sheet.new_page()

    # --- Page 2: letterhead + organic section, two independent column streams.
    sheet.text(LEFT_X, 40, "VAN-WHOLE PRODUCE", font="Helvetica-Bold", size=12)
    sheet.text(470, 46, "Aug 24 - 26, 2026")
    sheet.text(LEFT_X, 66, "830 MALKIN AVENUE, VANCOUVER, BC, V6A 2K2")
    sheet.text(LEFT_X, 84, "TEL: (604) 251-3330 FAX: (604) 258-5544")
    sheet.text(
        LEFT_X, 112, "PRICE SUBJECT TO CHANGE DUE TO MARKET CONDITIONS", font="Helvetica-Bold"
    )
    sheet.text(LEFT_X, 150, "Organic Fruits and Vegetable")

    sheet.header(LEFT_X, 180, "FRUITS")
    sheet.header(RIGHT_X, 180, "HERB")

    sheet.text(LEFT_X, 205, "AVOCADOS ORGANIC MEX 20S")
    sheet.price(LEFT_PRICE_X1, 205, "31.75")
    sheet.text(RIGHT_X, 205, "BASIL ORGANIC CALIF 12S")
    sheet.price(RIGHT_PRICE_X1, 205, "42.75")

    sheet.text(LEFT_X, 225, "BANANAS ORGANIC ECU 40 LBS")
    sheet.price(LEFT_PRICE_X1, 225, "53.75")

    sheet.header(LEFT_X, 250, "VEGETABLES")

    sheet.text(LEFT_X, 275, "CARROTS ORGANIC BC 25 LBS")
    sheet.price(LEFT_PRICE_X1, 275, "23.25")

    sheet.text(300, 975, "2")  # page number footer
    sheet.new_page()

    # --- Page 3: conventional section, no repeated letterhead, edge cases.
    sheet.header(LEFT_X, 40, "FRUITS")
    sheet.header(RIGHT_X, 40, "VEGETABLES")

    sheet.text(LEFT_X, 65, "MANGOS PREMIUM MEX 10S")
    sheet.price(LEFT_PRICE_X1, 65, "38.50")
    sheet.text(RIGHT_X, 65, "PEPPERS RED BC 11LBS")
    sheet.price(RIGHT_PRICE_X1, 65, "34.00")

    sheet.text(LEFT_X, 90, "GINGER ROOT PERU PER LB")  # -> price_basis "lb"
    sheet.price(LEFT_PRICE_X1, 90, "2.60")
    sheet.text(RIGHT_X, 90, "SQUASH BUTTERNUT CALIF 40LBS")
    sheet.price(RIGHT_PRICE_X1, 90, "28.50")

    sheet.text(LEFT_X, 115, "TURMERIC ROOT ORGANIC 12X227G")  # -> unavailable
    sheet.price(LEFT_PRICE_X1, 115, "N/A")

    sheet.header(LEFT_X, 140, "MUSHROOMS")  # not in the canonical list -> unknown_section warning

    sheet.text(LEFT_X, 165, "MUSHROOMS WHITE NO1 BC (48213)")  # -> supplier_sku "48213"
    sheet.price(LEFT_PRICE_X1, 165, "24.50")

    # Orphan price: description on one line, price alone 5pt below -> merge_orphan_prices.
    # (Kept narrow enough to stay inside the left column - a wider string would
    # spill words past the x306 gutter and land in the right column instead.)
    sheet.text(LEFT_X, 190, "SALAD MIX BABY GREENS (E.B.) 5510097")
    sheet.price(LEFT_PRICE_X1, 195, "29.75")

    sheet.text(300, 975, "3")  # page number footer
    sheet.new_page()

    c.save()
    sheet.buf.seek(0)
    return sheet.buf.getvalue()


def main() -> None:
    out = pathlib.Path(__file__).parent / "synthetic.pdf"
    out.write_bytes(build())
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
