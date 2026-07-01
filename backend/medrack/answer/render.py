"""Render single-question preview PDFs for the answer pipeline."""
import os
import re
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from medrack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# OCR declump: clean up words that lost their spaces during PDF extraction
# (e.g. "Def initionofhealthgivenbyWHO" -> "Definition of health given by WHO").
# We use two strategies:
#   1. Split on existing whitespace (those are reliable word boundaries).
#   2. For joined runs of letters, use a dictionary-based DP to insert
#      spaces between known English words.
#   3. As a fallback, insert a space before any uppercase letter that is
#      preceded by a lowercase letter and followed by a lowercase letter
#      (the lUl pattern from camelCase: "ofHealth" -> "of Health").
# ---------------------------------------------------------------------------

_WORDLIST: set[str] | None = None
_MEDICAL_TERMS: set[str] = set("""
health disease definition indicator factor classification country
life medical medicine public community hospital patient care doctor nurse
symptom sign diagnosis treatment therapy prevention remedy
epidemic pandemic endemic infection virus bacteria parasite
cancer tumor heart lung liver kidney brain blood smoking alcohol
drug diet exercise stress sleep weight child adult elderly infant
adolescent pregnancy birth fertility mortality morbidity disability
vaccine vaccination immunization antibiotic rate ratio case fatality
maternal infant expectancy standard lifestyle diseases
primary secondary tertiary right role impact causality causation
criteria association correlation promote promotion wellbeing
physical mental social dimension economic world health
united nations mission program policy sustainable development
millennium genetic heredity environment occupation income literacy
sanitation water immunization
""".lower().split())


def _get_wordlist() -> set[str]:
    """Load a system wordlist once. Falls back to a small built-in set."""
    global _WORDLIST
    if _WORDLIST is not None:
        return _WORDLIST
    words: set[str] = set()
    for p in ("/usr/share/dict/words", "/usr/share/dict/american-english",
              "/usr/share/dict/british-english"):
        if os.path.exists(p):
            try:
                with open(p) as f:
                    for line in f:
                        w = line.strip()
                        if w and 2 <= len(w) <= 25 and w == w.lower() and w.isalpha():
                            words.add(w)
            except OSError:
                pass
            break
    words |= _MEDICAL_TERMS
    _WORDLIST = words
    return _WORDLIST


def _segment_run(run: str) -> str:
    """DP-based segmentation of one run of letters (no internal spaces).
    Returns the run with spaces inserted between recognized words, or the
    original run unchanged if no segmentation helps.
    """
    n = len(run)
    if n <= 4:
        return run
    words = _get_wordlist()
    # best[i] = max chars covered by a sequence of words in run[0:i]
    best = [0] * (n + 1)
    # back[i] = start position of the last word in the optimal seq
    # ending at i, or -1 if best[i] == best[i-1] (no improvement).
    back = [-1] * (n + 1)
    for i in range(1, n + 1):
        best[i] = best[i - 1]
        for j in range(max(0, i - 25), i):
            chunk = run[j:i]
            cl = chunk.lower()
            if cl in words and len(chunk) >= 2:
                cov = best[j] + len(chunk)
                if cov > best[i]:
                    best[i] = cov
                    back[i] = j
    if best[n] < int(n * 0.6):
        return run
    # Reconstruct: walk back from n, recording each word's (start, end).
    # At each step: if back[i] == -1, no match ended exactly at i; step
    # back to i-1 and re-check. Otherwise, record (back[i], i), and
    # jump to back[i] (the start of that word) to continue.
    words_found: list[tuple[int, int]] = []  # (start, end) pairs
    i = n
    visited = 0
    while i > 0 and visited < n + 2:
        visited += 1
        if back[i] >= 0:
            words_found.append((back[i], i))
            i = back[i]
        else:
            i -= 1
    if not words_found:
        return run
    # We walked back; the words are in reverse order. We need to know
    # the START of each word to know what comes before. The algorithm
    # above gives us the start, so we have (start, end) pairs. The next
    # word's start is the previous end - len_of_word. Actually the
    # correct way: reverse the list, then we have words in order
    # (start0, end0), (start1, end1), ... where end0 = start1. We need
    # to walk forward to reconstruct.
    words_found.sort()
    # Build the output by emitting the run with spaces at boundaries
    # (start, end) of each word.
    out: list[str] = []
    cursor = 0
    for start, end in words_found:
        if cursor < start:
            out.append(run[cursor:start])
        out.append(run[start:end])
        cursor = end
    if cursor < n:
        out.append(run[cursor:])
    return " ".join(p for p in out if p)


# Camel-case split: "ofHealth" -> "of Health". Catches the most common
# OCR artifact (uppercase letter in the middle of a word).
_CAMEL_RE = re.compile(r"([a-z])([A-Z])([a-z])")


def _declump_token(tok: str) -> str:
    """De-clump one whitespace-separated token (no internal spaces)."""
    if not tok or len(tok) <= 3:
        return tok
    if not all(c.isalpha() for c in tok):
        return tok
    if tok.isupper():
        return tok  # probably an acronym like WHO
    # Step 1: split on camel-case
    tok2 = _CAMEL_RE.sub(r"\1 \2\3", tok)
    if " " in tok2:
        # Each piece is now a candidate; re-segment the joined piece
        # (the one without the original first character).
        prefix, rest = tok2.split(" ", 1)
        if rest:
            return prefix + " " + _segment_run(rest)
        return tok2
    # Step 2: no camel-case, try DP
    return _segment_run(tok)


def de_garble_text(text: str) -> str:
    """De-garble a question / answer text using the strategies above.

    Returns the original text unchanged if no improvement is found.
    """
    if not text:
        return text
    # First pass: join the first 1-2 char token with the next token if
    # the next token starts with a lowercase letter. Catches the
    # "M ostimportant" -> "M ost important" OCR artifact.
    tokens = text.split(" ")
    fixed_tokens: list[str] = []
    i = 0
    while i < len(tokens):
        if (
            i + 1 < len(tokens)
            and len(tokens[i]) <= 2
            and tokens[i].isalpha()
            and tokens[i + 1]
            and tokens[i + 1][0].isalpha()
            and tokens[i + 1][0].islower()
        ):
            merged = tokens[i] + tokens[i + 1]
            if all(c.isalpha() for c in merged):
                fixed_tokens.append(merged)
                i += 2
                continue
        fixed_tokens.append(tokens[i])
        i += 1
    # Second pass: declump each merged token.
    out = [_declump_token(t) for t in fixed_tokens]
    return " ".join(out)


def _build_styles():
    """Build the paragraph styles used by the preview PDF.

    The visual style mirrors the K. Park answer-bank reference PDF:
    page header bar, centered section subheader, numbered Q heading,
    plain text headings (no ** bold), hanging-indent bullets with the
    bullet glyph inline, and a centred page footer.
    """
    base = getSampleStyleSheet()
    # Top page header: "COMMUNITY MEDICINE | Chapter 1: Concept..."
    # Small caps, centred, with bottom border.
    page_header = ParagraphStyle(
        "PageHeader",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        alignment=TA_CENTER,
        textColor=HexColor("#3a3a3a"),
        spaceAfter=2,
    )
    # Big title: "Community Medicine – Exam Answers"
    title = ParagraphStyle(
        "DocTitle",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=4,
        textColor=HexColor("#1a3a6c"),
    )
    # Subtitle: "Chapter 1 • Concept of Health & Disease"
    subtitle = ParagraphStyle(
        "Subtitle",
        parent=base["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=11,
        alignment=TA_CENTER,
        spaceAfter=4,
        textColor=HexColor("#555555"),
    )
    # Section subheader: "Section C – Long Answers (10 marks)"
    # Centred, with a horizontal rule above and below.
    section_subheader = ParagraphStyle(
        "SectionSubheader",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        alignment=TA_CENTER,
        spaceBefore=10,
        spaceAfter=10,
        textColor=HexColor("#1a3a6c"),
    )
    # Section label inside the body: "Question:", "Answer:", etc.
    section_label = ParagraphStyle(
        "SectionLabel",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        spaceBefore=10,
        spaceAfter=4,
        textColor=HexColor("#1a3a6c"),
    )
    # Question number + text: "Q1. <cleaned text>"
    question_text = ParagraphStyle(
        "QuestionText",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=11.5,
        leading=15,
        spaceAfter=8,
        leftIndent=4,
    )
    body = ParagraphStyle(
        "PreviewBody",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        spaceAfter=6,
    )
    option = ParagraphStyle(
        "OptionLine",
        parent=body,
        leftIndent=18,
        spaceAfter=2,
    )
    # Hanging-indent bullet used in the LLM answer.
    bullet = ParagraphStyle(
        "AnswerBullet",
        parent=body,
        leftIndent=24,
        bulletIndent=6,
        spaceBefore=2,
        spaceAfter=4,
        leading=15,
    )
    sub_bullet = ParagraphStyle(
        "AnswerSubBullet",
        parent=bullet,
        leftIndent=44,
        bulletIndent=26,
        fontSize=10.5,
    )
    # Section heading inside the answer body. Per the operator's request
    # we use the K. Park sample style: plain text (NOT bold, no **) with
    # a ":-" suffix added by the renderer (e.g. "Definition:-",
    # "Justification -", "Classification of indicators:-"). The ":-"
    # suffix is appended by render_preview_pdf when emitting the heading.
    answer_heading = ParagraphStyle(
        "AnswerHeading",
        parent=base["Normal"],
        fontName="Helvetica",  # NOT bold (operator asked for plain text)
        fontSize=12,
        spaceBefore=14,
        spaceAfter=4,
        textColor=HexColor("#1a3a6c"),
    )
    # Final "exam-prep study notes" line at the bottom of the answer.
    study_note = ParagraphStyle(
        "StudyNote",
        parent=base["Italic"],
        fontName="Helvetica-Oblique",
        fontSize=10,
        textColor=HexColor("#666666"),
        spaceBefore=8,
        spaceAfter=4,
    )
    # Page footer: "Page N"
    page_footer = ParagraphStyle(
        "PageFooter",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        alignment=TA_CENTER,
        textColor=HexColor("#888888"),
    )
    # (The "Exam-prep study notes" footer was removed in v5.2 per
    # operator request. We keep the style around in case it's needed
    # for non-preview PDFs, but the study_note is no longer emitted.)

    return {
        "page_header": page_header,
        "title": title,
        "subtitle": subtitle,
        "section_subheader": section_subheader,
        "section_label": section_label,
        "question_text": question_text,
        "body": body,
        "option": option,
        "bullet": bullet,
        "sub_bullet": sub_bullet,
        "answer_heading": answer_heading,
        "study_note": study_note,
        "page_footer": page_footer,
    }


def _safe_text(text: str) -> str:
    """Escape characters that reportlab's Paragraph parser treats as markup.

    We pass the LLM's answer text through verbatim, but we must escape
    `<`, `>`, and `&` so reportlab doesn't choke on stray angle brackets.
    We also convert markdown bold (``**word**``) and italic (``*word*``)
    markers to reportlab's ``<b>...</b>`` and ``<i>...</i>`` tags so they
    actually render as bold/italic in the PDF.

    Per the operator's request, we also strip inline source citations
    like ``(WHO)``, ``(Park 27e)``, ``(ICMR)``, etc. — this is exam
    prep, not a literature review. We remove parens that contain only
    a source reference (with optional version/edition).
    """
    if not text:
        return ""
    out = text
    # Strip inline source citations: (WHO), (Park 27e), (Park 27 ed.),
    # (ICMR), (NFHS-5), (SRS 2020), (Ottawa Charter), (Alma-Ata 1978), etc.
    # Heuristic: a parenthesised group whose content is a short
    # (1-3 words) source-like phrase: starts with uppercase, has at most
    # 3 internal spaces, contains at least one uppercase letter and
    # either a digit or ends in a known source suffix.
    out = re.sub(
        r"\s*\(\s*(?:[A-Z][A-Za-z\-]*(?:\s+[A-Za-z0-9\-]+){0,3}"
        r"(?:\s+(?:19|20)\d{2})?)\s*\)",
        "",
        out,
    )
    # Convert **word** (markdown bold) to <b>word</b>. We do this
    # BEFORE escaping & so the inserted tags aren't double-escaped.
    out = re.sub(r"\*\*([^*\n]+?)\*\*", r"<b>\1</b>", out)
    # Convert *word* (markdown italic) to <i>word</i>. Skip matches
    # that are part of a ** pair (already handled above).
    out = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", out)
    # Now escape the special chars.
    out = (out
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;"))
    # ... but we want our <b> and <i> tags to remain as actual tags,
    # not be escaped. Restore them.
    out = out.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    out = out.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
    return out


# Lines that start with a bullet glyph. We support the three the LLM
# commonly emits: "•" (U+2022), "–" (U+2013 en-dash, for sub-bullets),
# and "-" (ASCII, fallback).
_BULLET_RE = re.compile(r"^\s*([•\-\u2013\u2014])\s*(.*)$")
# Markdown-style bullets ("* item", "+ item"). A space is REQUIRED after the
# marker so a "**bold**" heading line is never mistaken for a bullet. ("-" is
# already covered by _BULLET_RE above.)
_MD_BULLET_RE = re.compile(r"^\s*([*+])\s+(.*)$")
# Lines that look like a section heading: short, don't end with a
# period, no leading bullet, may be **bold** or prefixed with ### (which
# some LLMs emit even when told not to).
_HEADING_RE = re.compile(
    r"^#{1,6}\s*(.+?)\s*#{0,6}$"  # optional leading ### (and matching trailing)
    r"|"
    r"^([A-Z][A-Za-z0-9 \-/&,'()–—\-]{1,80})$"
)


def _classify_line(line: str) -> tuple[str, str]:
    """Return (kind, content) for one line of the LLM answer.

    kinds: "main_bullet", "sub_bullet", "heading", "paragraph"
    """
    stripped = line.strip()
    if not stripped:
        return ("blank", "")
    # A markdown bold-only line like "**Health Problems of Adolescents**" is a
    # section heading — some generations use **bold** for headings instead of
    # plain text. (Checked before bullets so it isn't caught as a "* " bullet.)
    mhead = re.match(r"^\*\*\s*(.+?)\s*\*\*[:.]?$", stripped)
    if mhead:
        return ("heading", mhead.group(1).strip())
    m = _BULLET_RE.match(line) or _MD_BULLET_RE.match(line)
    if m:
        bullet, rest = m.group(1), m.group(2).strip()
        if bullet in ("–", "—", "-"):
            return ("sub_bullet", rest)
        return ("main_bullet", rest)
    # Heading heuristic: short, starts with capital, no terminal
    # punctuation (., :, ;). Section headings in the sample are
    # plain text like "Definition", "Justification – why a healthy
    # lifestyle is central to health promotion", etc.
    if _HEADING_RE.match(stripped) and not stripped.endswith((".", ":", ";")):
        # Strip any leading / trailing ### that the LLM emitted
        # despite being told not to use markdown headers.
        cleaned = re.sub(r"^#+\s*", "", stripped)
        cleaned = re.sub(r"\s*#+\s*$", "", cleaned)
        return ("heading", cleaned)
    return ("paragraph", stripped)


def _is_table_separator(line: str) -> bool:
    """True for a Markdown table separator row like ``|---|---|`` / ``| :-- | --: |``."""
    s = line.strip()
    if "-" not in s or "|" not in s:
        return False
    cells = s.strip("|").split("|")
    return bool(cells) and all(re.match(r"^\s*:?-{1,}:?\s*$", c) for c in cells)


def _split_table_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _split_answer_blocks(answer_text: str) -> list:
    """Parse the LLM answer into ordered ``(kind, content)`` blocks.

    ``kind`` is ``main_bullet`` / ``sub_bullet`` / ``heading`` / ``paragraph``
    (content is a ``str``) or ``table`` (content is ``list[list[str]]`` — the
    first row is the header). Blank lines separate blocks.
    """
    lines = answer_text.split("\n")
    blocks: list = []
    current_kind: str | None = None
    current_buf: list[str] = []

    def flush():
        nonlocal current_kind, current_buf
        if current_kind is None or not current_buf:
            current_kind, current_buf = None, []
            return
        if current_kind in ("main_bullet", "sub_bullet", "heading"):
            for line in current_buf:
                blocks.append((current_kind, line))
        else:
            blocks.append((current_kind, " ".join(current_buf)))
        current_kind, current_buf = None, []

    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        # A fenced Graphviz/DOT flowchart block: ```dot ... ```
        if re.match(r"^\s*`{3,}\s*(dot|graphviz)\s*$", line, re.IGNORECASE):
            flush()
            dot_lines: list[str] = []
            j = i + 1
            while j < n and not re.match(r"^\s*`{3,}\s*$", lines[j]):
                dot_lines.append(lines[j])
                j += 1
            blocks.append(("diagram", "\n".join(dot_lines)))
            i = j + 1  # skip the closing fence
            continue
        # A Markdown table: a row with '|' whose NEXT line is a separator.
        if "|" in line and i + 1 < n and _is_table_separator(lines[i + 1]):
            flush()
            rows = [_split_table_row(line)]
            j = i + 2
            while (
                j < n
                and lines[j].strip()
                and "|" in lines[j]
                and not _is_table_separator(lines[j])
            ):
                rows.append(_split_table_row(lines[j]))
                j += 1
            blocks.append(("table", rows))
            i = j
            continue

        kind, content = _classify_line(line)
        if kind == "blank":
            flush()
            i += 1
            continue
        if current_kind is None:
            current_kind = kind
            current_buf.append(content)
        elif current_kind == kind:
            current_buf.append(content)
        else:
            flush()
            current_kind = kind
            current_buf.append(content)
        i += 1
    flush()
    return blocks


def _make_table_flowable(rows: list, avail_width: float):
    """Build a styled reportlab ``Table`` from parsed markdown rows (row 0 =
    header). Returns ``None`` if there is nothing to render."""
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors as _colors

    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        return None
    ncols = max(len(r) for r in rows)
    rows = [list(r) + [""] * (ncols - len(r)) for r in rows]
    head = ParagraphStyle(
        "TblHead", fontName="Helvetica-Bold", fontSize=9, leading=11.5,
        textColor=_colors.white,
    )
    cell = ParagraphStyle(
        "TblCell", fontName="Helvetica", fontSize=9, leading=11.5,
        textColor=HexColor("#1a1a1a"),
    )
    data = [
        [Paragraph(_safe_text(str(c or "")), head if ri == 0 else cell) for c in row]
        for ri, row in enumerate(rows)
    ]
    colw = max(42.0, avail_width / ncols)
    tbl = Table(data, colWidths=[colw] * ncols, hAlign="LEFT", repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1a3a6c")),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#b9c2d0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_colors.white, HexColor("#eef2f7")]),
            ]
        )
    )
    return tbl


def render_dot_to_png(dot_source: str, dpi: int = 150) -> bytes | None:
    """Render Graphviz DOT source to PNG bytes via the ``dot`` CLI.

    Returns ``None`` if graphviz is unavailable or the DOT is invalid — so a
    bad model-generated flowchart never breaks the answer.
    """
    import shutil
    import subprocess

    if not dot_source or not dot_source.strip() or not shutil.which("dot"):
        return None
    try:
        proc = subprocess.run(
            ["dot", "-Tpng", f"-Gdpi={dpi}"],
            input=dot_source.encode("utf-8"),
            capture_output=True,
            timeout=15,
        )
    except Exception:  # noqa: BLE001
        return None
    if proc.returncode != 0 or not proc.stdout:
        log.warning("graphviz dot failed: %s", (proc.stderr or b"")[:200])
        return None
    return proc.stdout


def _make_diagram_flowable(dot_source: str, avail_width: float):
    """Render a DOT flowchart to a page-fitted reportlab ``Image`` (or None)."""
    png = render_dot_to_png(dot_source)
    if not png:
        return None
    import io

    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image

    try:
        iw, ih = ImageReader(io.BytesIO(png)).getSize()
    except Exception:  # noqa: BLE001
        return None
    if not iw or not ih:
        return None
    dpi = 150.0
    natural_w = iw * 72.0 / dpi
    natural_h = ih * 72.0 / dpi
    scale = min(avail_width / natural_w, 1.0)
    img = Image(io.BytesIO(png), width=natural_w * scale, height=natural_h * scale)
    img.hAlign = "CENTER"
    return img


def clean_answer_text(text: str) -> str:
    """Tidy a possibly-truncated answer before rendering.

    A generation that hits the token cap can end mid-word with an unclosed
    bold marker (e.g. ``... To provide **coun``). This strips a dangling
    unfinished bold fragment and drops a final bullet line that was clearly
    cut off (no terminal punctuation), so the PDF never shows a raw ``**``
    or a half word.
    """
    text = (text or "").rstrip()
    if not text:
        return text
    truncated = False
    # Dangling unclosed bold from truncation -> drop the short fragment.
    if text.count("**") % 2 == 1:
        idx = text.rfind("**")
        if idx != -1 and (len(text) - idx) <= 80:
            text = text[:idx].rstrip()
            truncated = True
    # Only when we detected a truncation, also drop the now-incomplete final
    # bullet if it's a short fragment or lacks terminal punctuation. A clean
    # answer (balanced bold) is never modified, so legitimate unpunctuated
    # last lines are preserved.
    if truncated:
        lines = text.split("\n")
        if lines:
            last = lines[-1].strip()
            words = re.sub(r"^[•\-–—*]\s*", "", last).split()
            if re.match(r"^[•\-–—*]", last) and (
                len(words) < 5 or last[-1:] not in (".", "!", "?", ":", ")", "]", '"')
            ):
                text = "\n".join(lines[:-1]).rstrip()
    return text


def render_preview_pdf(
    output_path: Path,
    *,
    module_name: str,
    module_subject: str,
    chapter: str = "",         # e.g. "chapter 1" — used in the page header
    question: dict,           # from extracted.json: {"qid", "question_text", "type", "options", ...}
    answer: dict,            # from cache: {"answer_text", "retrieval_chunks", ...}
    question_index: int,     # 1-indexed position in the module
    total_questions: int,    # total questions in the requested scope
    marks: int | None = None, # 5 or 10 — used to label "Section C/D" and "marks"
) -> None:
    """Render a preview PDF for a single question.

    Layout (mirrors the K. Park answer-bank reference PDF):
      1. Top page header: "COMMUNITY MEDICINE | Chapter 1: Concept..."
      2. Big title: "Community Medicine – Exam Answers"
      3. Subtitle: "Module psm-module-1 • Chapter 1"
      4. Section subheader: "Section C – Long Answers (10 marks)" with rules
      5. Numbered question: "Q1. <cleaned text>"
      6. (MCQ only) options list
      7. Answer with bullets, sub-bullets, plain-text headings ending in ":-"
      8. Study-notes footer: "Exam-prep study notes – write in your own hand..."
      9. Page footer: "Page N"
    """
    from reportlab.lib.units import inch as _inch
    from reportlab.platypus import (
        PageBreak, KeepTogether, HRFlowable,
    )
    from reportlab.pdfgen import canvas as _canvas

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()
    story = []

    # ---- 1. Top page header ----
    page_header_text = (
        f"COMMUNITY MEDICINE {chr(0x7C)} Module {module_name}"
        + (f" {chr(0x2022)} {chapter.title()}" if chapter else "")
    )
    story.append(Paragraph(page_header_text, styles["page_header"]))
    story.append(HRFlowable(width="100%", thickness=0.7,
                             color=HexColor("#888888"),
                             spaceBefore=0, spaceAfter=4))

    # ---- 2. Big title + 3. subtitle ----
    story.append(Paragraph("Community Medicine \u2013 Exam Answers",
                           styles["title"]))
    subtitle_text = f"Module {module_name} \u2022 {module_subject.upper()}"
    if chapter:
        subtitle_text += f" \u2022 {chapter.title()}"
    story.append(Paragraph(subtitle_text, styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=HexColor("#cccccc"),
                             spaceBefore=4, spaceAfter=4))

    # ---- 4. Section subheader (5-mark vs 10-mark) ----
    if marks is None:
        marks = 10
    if marks >= 10:
        section_label_text = f"Section C \u2013 Long Answers ({marks} marks)"
    else:
        section_label_text = f"Section D \u2013 Short Answers ({marks} marks)"
    story.append(Paragraph(section_label_text,
                           styles["section_subheader"]))

    # ---- 5. Question ----
    # Extract the numeric portion of qid for the "Q1." display (e.g. q022 -> Q22).
    qid_raw = question.get("qid", "q000")
    qid_digits = "".join(c for c in qid_raw if c.isdigit())
    qid_num = int(qid_digits) if qid_digits else question_index
    story.append(Paragraph("Question:", styles["section_label"]))
    # De-clump the question text: split on existing whitespace, then
    # re-segment joined runs.
    raw_q = question.get("question_text", "") or ""
    cleaned_q = de_garble_text(raw_q)
    # Strip any trailing ":-" the LLM might have emitted (defensive)
    cleaned_q = re.sub(r"\s*[:\-]+\s*$", "", cleaned_q).strip()
    q_text = _safe_text(cleaned_q or raw_q)
    story.append(Paragraph(f"Q{qid_num}. {q_text}",
                           styles["question_text"]))
    story.append(Spacer(1, 4))

    # ---- 6. MCQ options (if any) ----
    if question.get("type") == "mcq" and question.get("options"):
        options = question["options"]
        for letter in sorted(options.keys()):
            opt_text = _safe_text(de_garble_text(options[letter]))
            line = f"\u2022 {letter}) {opt_text}"
            story.append(Paragraph(line, styles["option"]))
        story.append(Spacer(1, 6))

    # ---- 7. Answer body ----
    story.append(Paragraph("Answer:", styles["section_label"]))
    answer_text = clean_answer_text(answer.get("answer_text", ""))
    if not answer_text.strip():
        story.append(Paragraph("(no answer text)", styles["body"]))
    else:
        for kind, content in _split_answer_blocks(answer_text):
            if kind == "main_bullet":
                story.append(Paragraph(
                    "\u2022 " + _safe_text(content), styles["bullet"]
                ))
            elif kind == "sub_bullet":
                story.append(Paragraph(
                    "\u2013 " + _safe_text(content), styles["sub_bullet"]
                ))
            elif kind == "heading":
                # Plain text heading with ":-" suffix (no **). Strip any
                # existing ":-" / ":-" / ":" / " -" suffix to avoid
                # duplication, then re-add exactly one ":-".
                head = re.sub(r"\s*[:\-]+\s*$", "", content).strip()
                if head:
                    head = head + ":-"
                story.append(Paragraph(
                    _safe_text(head), styles["answer_heading"]
                ))
            elif kind == "table":
                tbl = _make_table_flowable(content, LETTER[0] - 2 * _inch)
                if tbl is not None:
                    story.append(Spacer(1, 3))
                    story.append(tbl)
                    story.append(Spacer(1, 6))
            elif kind == "diagram":
                img = _make_diagram_flowable(content, LETTER[0] - 2 * _inch)
                if img is not None:
                    story.append(Spacer(1, 4))
                    story.append(img)
                    story.append(Spacer(1, 6))
            else:  # paragraph
                story.append(Paragraph(
                    _safe_text(content), styles["body"]
                ))

    # (The "Exam-prep study notes" footer was removed in v5.2 per
    # operator request — the preview PDF should look like a clean
    # exam-ready answer, not include study notes.)

    # ---- Page numbers (rendered via on_page callback below) ----

    # Build the document. We use a custom on_page callback to draw the
    # "Page N" footer on every page (including pages 2+ that flow from
    # long answer bodies).
    def _on_page(canv: "_canvas.Canvas", doc) -> None:
        canv.saveState()
        # "Page N" centred at the bottom margin
        canv.setFont("Helvetica", 9)
        canv.setFillColor(HexColor("#888888"))
        page_num_text = f"Page {canv.getPageNumber()}"
        canv.drawCentredString(
            LETTER[0] / 2.0, 0.5 * _inch, page_num_text
        )
        # Top page header (re-render on every page)
        canv.setFont("Helvetica-Bold", 9)
        canv.setFillColor(HexColor("#3a3a3a"))
        canv.drawCentredString(LETTER[0] / 2.0, LETTER[1] - 0.5 * _inch,
                               page_header_text)
        canv.restoreState()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=1 * _inch,
        rightMargin=1 * _inch,
        topMargin=1 * _inch,
        bottomMargin=1 * _inch,
        title=f"Preview \u2014 {module_name} \u2014 Q{question_index}/{total_questions}",
    )
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    log.info("rendered preview pdf: %s (Q%d/%d)", output_path, question_index, total_questions)
