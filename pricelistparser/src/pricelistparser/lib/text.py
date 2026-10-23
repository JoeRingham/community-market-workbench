"""Text helpers: section-header detection and letter-spacing normalization."""

from __future__ import annotations

import re
import statistics

# A run of single-character words separated by wide gaps is a letter-spaced
# section header (e.g. "S A L A D  -  T A Y L O R  F A R M").
_SPACE_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"

# "Aug 24 - 26, 2026"  or  "Aug 30 - Sep 1, 2026"
DATE_RANGE_RE = re.compile(
    rf"\b({_SPACE_MONTHS})\s+(\d{{1,2}})\s*[-–]\s*(?:({_SPACE_MONTHS})\s+)?(\d{{1,2}}),\s*(\d{{4}})\b"
)


def looks_like_section_header(word_texts: list[str], *, min_words: int = 3) -> bool:
    """True when most tokens on the line are single characters."""
    toks = [t for t in word_texts if t.strip()]
    if len(toks) < min_words:
        return False
    singles = sum(1 for t in toks if len(t) == 1)
    return singles / len(toks) >= 0.6


def reconstruct_spaced(words: list[dict]) -> str:
    """Rebuild a letter-spaced line into words.

    `words` are pdfplumber word dicts (need x0/x1/text). Letters within a word
    sit closer together than the gaps between words; a gap wider than ~2.2x the
    median gap is treated as a word boundary.
    """
    ws = sorted((w for w in words if w["text"].strip()), key=lambda w: w["x0"])
    if not ws:
        return ""
    if len(ws) == 1:
        return ws[0]["text"].strip()
    gaps = [ws[i + 1]["x0"] - ws[i]["x1"] for i in range(len(ws) - 1)]
    med = statistics.median(gaps) or 1.0
    out = [ws[0]["text"]]
    for i, gap in enumerate(gaps):
        out.append(" " if gap > med * 2.2 else "")
        out.append(ws[i + 1]["text"])
    return re.sub(r"\s+", " ", "".join(out)).strip()


def normalize_section(name: str) -> str:
    """Canonical form for a section label: upper, single-spaced, no trailing punctuation."""
    s = re.sub(r"\s+", " ", name).strip().upper()
    s = s.replace(" - ", " - ")  # keep hyphen groups readable
    return s.strip(" .:-")


def find_effective_range(text: str) -> tuple[str, str] | None:
    """Parse an effective date range from arbitrary header text.

    Returns (effective_from, effective_to) as ISO dates, or None. The year is
    taken from the trailing 4-digit group; the end month defaults to the start
    month when the range does not cross a month boundary.
    """
    m = DATE_RANGE_RE.search(text)
    if not m:
        return None
    start_mon, start_day, end_mon, end_day, year = m.groups()
    end_mon = end_mon or start_mon
    try:
        from datetime import date

        months = {mo: i + 1 for i, mo in enumerate(_SPACE_MONTHS.split("|"))}
        d_from = date(int(year), months[start_mon], int(start_day))
        d_to = date(int(year), months[end_mon], int(end_day))
        return d_from.isoformat(), d_to.isoformat()
    except (ValueError, KeyError):
        return None
