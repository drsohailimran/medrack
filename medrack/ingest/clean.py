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
    """Collapse letter-spaced tokens in a line.

    Walks through the line and collapses MAXIMAL RUNS of single-character
    alphabetic tokens. A "run" is a contiguous sequence of tokens that are
    each single alpha characters. Each run gets joined into one word.

    This handles the PSM Module 1 case where the entire page is one
    line with hundreds of tokens (e.g. "15. Vi r u l e n c e ... (a) Pro ...
    Key:c 16. Bu r d e n ...") — the per-line whole-string rule fails
    because the line also has multi-letter tokens like "mortality" and
    "rate". The per-run rule works because "Vi r u l e n c e" IS a
    maximal run of single-char tokens (15 in a row) and should be
    collapsed to "Virulence".

    Conservative: only collapse runs of ≥ 3 single-char tokens.
    Shorter runs are ambiguous (could be "I am a" with "I" and "a" as
    single chars but "am" as multi-char).
    """
    stripped = line.strip()
    if not stripped:
        return line

    tokens = stripped.split()
    if len(tokens) < 3:
        return line

    # Two cases the cleaner handles:
    #
    # Case A — all single-char tokens (e.g. "D E P A R T M E N T"):
    #   Apply the conservative whole-line rule: collapse when the joined
    #   string is at least 9 chars OR contains an uppercase letter.
    #   (a b c d e f g → joined "abcdefg" 7 chars, not collapsed;
    #    D E P A R T M E N T → joined "DEPARTMENT" 10 chars, collapsed.)
    #
    # Case B — multi-char token followed by single-char run (e.g. "Def i n i t i o n"):
    #   Always join, because the run is clearly the continuation of the
    #   previous word. This is the common pattern in PSM Module 1 and
    #   other Indian medical textbooks where the first word of a heading
    #   or option is not letter-spaced.
    single_char_indices = [k for k, t in enumerate(tokens) if len(t) == 1 and t.isalpha()]
    all_single = len(single_char_indices) == len(tokens)
    if all_single and len(tokens) >= 3:
        joined = "".join(tokens)
        has_upper = any(c.isupper() for c in joined)
        if has_upper or len(joined) > 8:
            return joined
        return line

    # Case B: walk and collapse runs of single-char tokens, joining with
    # any adjacent multi-char alpha token.
    result: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if len(t) == 1 and t.isalpha():
            j = i
            while j < len(tokens) and len(tokens[j]) == 1 and tokens[j].isalpha():
                j += 1
            run_len = j - i
            if run_len >= 3:
                run_text = "".join(tokens[i:j])
                if result and result[-1].isalpha() and len(result[-1]) > 1:
                    result[-1] = result[-1] + run_text
                else:
                    result.append(run_text)
                i = j
            else:
                result.append(t)
                i += 1
        else:
            result.append(t)
            i += 1

    return " ".join(result)


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
