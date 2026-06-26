"""Text cleaning for extracted or OCR'd PDF pages.

Pure functions, no I/O. Used by the KB ingest pipeline (Stage 2.2, T4) to
normalise page text after extraction/OCR and before chapter segmentation.
"""
from __future__ import annotations

import re

# A "Page N of M" footer line.
_PAGE_X_OF_Y_RE = re.compile(r"^Page\s+\d+\s+of\s+\d+$")
# A line that is just a number (page number, often header/footer).
_PURE_NUMBER_RE = re.compile(r"^\d+$")
# Collapse runs of 3+ newlines down to exactly 2.
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
# Collapse runs of 2+ spaces down to exactly 1.
_MULTI_SPACE_RE = re.compile(r" {2,}")
# Trailing whitespace at the end of a line (before \n).
_TRAILING_WS_RE = re.compile(r"[ \t]+(?=\n|$)")


def _collapse_letter_spacing_in_line(line: str) -> str:
    """Collapse a line of letter-spaced tokens into a single word.

    Heuristic (conservative):
      - Split on whitespace.
      - Require 90%+ of tokens to be single alphabetic characters.
      - Collapse only when the join makes sense:
          * The line contains at least one uppercase letter (heading/title), OR
          * All tokens are lowercase AND the joined string is > 8 chars
            (long enough that letter-spacing is the plausible reading).

    Returns the original line when no rule applies.
    """
    stripped = line.strip()
    if not stripped:
        return line

    tokens = stripped.split()
    if len(tokens) < 2:
        return line

    # All tokens must be pure alphabetic (no digits or punctuation). A line
    # like "I am a doctor" has multi-letter tokens, but more importantly a
    # line like "Foo 12 bar" would have a digit and must be left alone.
    if not all(t.isalpha() for t in tokens):
        return line

    single_char_count = sum(1 for t in tokens if len(t) == 1)

    # Two ways to qualify for collapse (either is enough):
    #   (i)  90%+ of the tokens are single characters, OR
    #   (ii) at least 5 tokens are single characters (catches cases like
    #        "Def i n i t i o n" where a 3-letter prefix drops the ratio
    #        below 90% but the line is clearly letter-spaced).
    ratio = single_char_count / len(tokens)
    if ratio < 0.9 and single_char_count < 5:
        return line

    joined = "".join(tokens)
    has_upper = any(c.isupper() for c in joined)
    all_lower = joined.isalpha() and joined.islower()

    if has_upper:
        return joined
    if all_lower and len(joined) > 8:
        return joined
    return line


def _is_header_or_footer_line(line: str) -> bool:
    """Return True for lines that look like page numbers or 'Page N of M' footers."""
    s = line.strip()
    if not s:
        return False
    if _PURE_NUMBER_RE.match(s):
        return True
    if _PAGE_X_OF_Y_RE.match(s):
        return True
    return False


def _strip_header_footer(text: str) -> str:
    """Remove lines that look like page headers/footers.

    The naive per-line approach: a bare number on its own line, or
    "Page N of M". Operates line by line, preserving blank-line structure
    so the later newline-collapse pass can squash the resulting gaps.
    """
    lines = text.split("\n")
    kept: list[str] = []
    for line in lines:
        if _is_header_or_footer_line(line):
            continue
        kept.append(line)
    return "\n".join(kept)


def clean_text(text: str) -> str:
    """Return cleaned text. Pure function, no I/O.

    Pipeline:
      1. Strip header/footer lines (pure numbers, "Page N of M").
      2. Collapse letter-spacing inside each remaining line.
      3. Collapse 3+ newlines to exactly 2.
      4. Strip trailing whitespace per line.
      5. Collapse multiple spaces to single.
      6. Strip leading/trailing whitespace on the whole text.
    """
    if not text:
        return ""

    # 1. Header/footer removal (do this before letter-spacing so a bare "42"
    #    doesn't get mistakenly consumed by a letter-spacing rule).
    text = _strip_header_footer(text)

    # 2. Letter-spacing collapse, line by line.
    text = "\n".join(_collapse_letter_spacing_in_line(line) for line in text.split("\n"))

    # 3. Collapse 3+ newlines → exactly 2.
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)

    # 4. Strip trailing whitespace per line.
    text = _TRAILING_WS_RE.sub("", text)

    # 5. Collapse multiple spaces to single (do this after newline collapse
    #    so we don't merge spaces across line boundaries into one long run
    #    that the newline rule would then squash into a single space).
    text = _MULTI_SPACE_RE.sub(" ", text)

    # 6. Strip leading/trailing whitespace on the whole text.
    return text.strip()


def clean_pages(pages: list[dict]) -> list[dict]:
    """Apply clean_text to the text of each page; return a new list of page dicts.

    The page's ``text`` is replaced with the cleaned text, and ``char_count``
    is recomputed to match ``len(text)``. Other fields are preserved as-is.
    """
    cleaned: list[dict] = []
    for page in pages:
        new_text = clean_text(page.get("text", ""))
        new_page = dict(page)
        new_page["text"] = new_text
        new_page["char_count"] = len(new_text)
        cleaned.append(new_page)
    return cleaned


__all__ = ["clean_text", "clean_pages"]
