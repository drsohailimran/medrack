"""Render single-question preview PDFs for the answer pipeline."""
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


def _build_styles():
    """Build the paragraph styles used by the preview PDF."""
    base = getSampleStyleSheet()
    header = ParagraphStyle(
        "PreviewHeader",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    module_line = ParagraphStyle(
        "ModuleLine",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=11,
        spaceAfter=12,
    )
    section_label = ParagraphStyle(
        "SectionLabel",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        spaceBefore=10,
        spaceAfter=4,
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
    # Bullet used in the LLM answer. We render each bullet on its own
    # line with a hanging indent so the wrapped text aligns under the
    # first character of the bullet content, matching the K. Park
    # sample style.
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
    # Section heading inside the answer body ("Definition",
    # "Justification – ...", "Classification", etc.). We render
    # without a bullet, in bold, with extra space before.
    answer_heading = ParagraphStyle(
        "AnswerHeading",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        spaceBefore=14,
        spaceAfter=4,
        textColor=HexColor("#222222"),
    )
    footer = ParagraphStyle(
        "PreviewFooter",
        parent=base["Italic"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        textColor=HexColor("#555555"),
        spaceBefore=18,
        alignment=TA_CENTER,
    )
    return {
        "header": header,
        "module_line": module_line,
        "section_label": section_label,
        "body": body,
        "option": option,
        "bullet": bullet,
        "sub_bullet": sub_bullet,
        "answer_heading": answer_heading,
        "footer": footer,
    }


def _safe_text(text: str) -> str:
    """Escape characters that reportlab's Paragraph parser treats as markup.

    We pass the LLM's answer text through verbatim (preserving ** markers),
    but we must escape `<`, `>`, and `&` so reportlab doesn't choke on stray
    angle brackets. Asterisks and other punctuation are left alone.
    """
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


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
    question: dict,           # from extracted.json: {"qid", "question_text", "type", "options", ...}
    answer: dict,            # from cache: {"answer_text", "retrieval_chunks", ...}
    question_index: int,     # 1-indexed position in the module
    total_questions: int,    # total questions in the requested scope
) -> None:
    """Render a preview PDF for a single question.

    Layout: A4 portrait, 1-inch margins, single column. Header on the first
    line, then module name + subject, the question text, the MCQ options
    (if present), the LLM's answer, and a footer noting this is a preview.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()
    story = []

    # Header
    header_text = (
        f"PREVIEW \u2014 Question {question_index} of {total_questions}"
    )
    story.append(Paragraph(header_text, styles["header"]))

    # Module line
    module_line = f"Module: {module_name} ({module_subject})"
    story.append(Paragraph(module_line, styles["module_line"]))

    # Question section
    story.append(Paragraph("Question:", styles["section_label"]))
    q_text = _safe_text(question.get("question_text", ""))
    story.append(Paragraph(q_text or "(no question text)", styles["body"]))
    story.append(Spacer(1, 6))

    # Options (if MCQ)
    if question.get("type") == "mcq" and question.get("options"):
        options = question["options"]
        for letter in sorted(options.keys()):
            line = f"\u2022 {letter}) {_safe_text(options[letter])}"
            story.append(Paragraph(line, styles["option"]))
        story.append(Spacer(1, 6))

    # Answer section
    story.append(Paragraph("Answer:", styles["section_label"]))
    answer_text = answer.get("answer_text", "")
    if not answer_text.strip():
        story.append(Paragraph("(no answer text)", styles["body"]))
    else:
        # Split the LLM answer into blocks and render each one with
        # appropriate styling. This is the key fix: previously the
        # entire answer was passed as one Paragraph, which collapsed
        # all newlines and made the PDF look like one big blob.
        for kind, content in _split_answer_blocks(answer_text):
            if kind == "main_bullet":
                # "•" prefix in the LLM output; we re-add it via
                # the bullet text since reportlab's bulletText
                # feature is fiddly. Use safe text + bullet glyph.
                story.append(Paragraph(
                    "\u2022 " + _safe_text(content), styles["bullet"]
                ))
            elif kind == "sub_bullet":
                story.append(Paragraph(
                    "\u2013 " + _safe_text(content), styles["sub_bullet"]
                ))
            elif kind == "heading":
                story.append(Paragraph(
                    _safe_text(content), styles["answer_heading"]
                ))
            else:  # paragraph
                story.append(Paragraph(
                    _safe_text(content), styles["body"]
                ))

    # Footer
    footer_text = (
        "This is a preview. Run `medrack approve` to generate the rest."
    )
    story.append(Paragraph(footer_text, styles["footer"]))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,  # A4-portrait-like; reportlab defaults to LETTER in US. Using
                          # LETTER keeps the prototype simple and matches test fixtures.
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
        title=f"Preview — {module_name} — Q{question_index}/{total_questions}",
    )

    doc.build(story)
    log.info("rendered preview pdf: %s (Q%d/%d)", output_path, question_index, total_questions)
