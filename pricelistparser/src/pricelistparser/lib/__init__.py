"""Shared, supplier-neutral geometry and text helpers for raw-extraction parsers.

Most PDF price lists are variations on the same problem — a page split into
columns, rows aligned by baseline, a right-aligned price. Supplier modules
supply the constants (column split x, price anchors, furniture patterns) and
lean on these helpers for the mechanics.
"""
