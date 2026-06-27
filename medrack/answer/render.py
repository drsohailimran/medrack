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
    m = _BULLET_RE.match(line)
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


def _split_answer_blocks(answer_text: str) -> list[tuple[str, str]]:
    """Parse the LLM answer into a list of (kind, content) blocks.

    Blank lines separate blocks. A block can be:
      - a single bullet / sub-bullet
      - a section heading (no bullet)
      - a paragraph (multi-line text wrapped)
    """
    lines = answer_text.split("\n")
    blocks: list[tuple[str, str]] = []
    current_kind: str | None = None
    current_buf: list[str] = []

    def flush():
        nonlocal current_kind, current_buf
        if current_kind is None or not current_buf:
            return
        if current_kind in ("main_bullet", "sub_bullet", "heading"):
            # Each bullet / heading is its own block.
            for line in current_buf:
                blocks.append((current_kind, line))
        else:
            # Paragraph: join the lines.
            blocks.append((current_kind, " ".join(current_buf)))
        current_kind = None
        current_buf = []

    for line in lines:
        kind, content = _classify_line(line)
        if kind == "blank":
            flush()
            continue
        if current_kind is None:
            current_kind = kind
            current_buf.append(content)
        elif current_kind == kind:
            current_buf.append(content)
        else:
            # Kind changed mid-block (e.g. bullet followed by heading).
            # Flush what we have, then start a new block.
            flush()
            current_kind = kind
            current_buf.append(content)
    flush()
    return blocks


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
    answer_text = answer.get("answer_text", "")
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
