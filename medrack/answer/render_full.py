"""Render full module PDFs for the answer pipeline (Stage 2.5 B2).

Layout: A4 portrait, 1-inch margins. The PDF has:
- Cover page: module name, subject, total questions, generated date.
- Table of contents: list of questions with placeholder page numbers.
- Per-question pages: one per answer in `answers`, laid out like the
  Stage 2.4 preview PDF (header, question, options if MCQ, answer, footer).
- Index page (last page): all question IDs and a short tag for each.

We do NOT modify `medrack.answer.render.render_preview_pdf` (Stage 2.4) per
the brief — we inline the per-question flowables here.
"""
from datetime import datetime
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from medrack.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------


def _build_styles():
    """Build the paragraph styles used by the full module PDF."""
    base = getSampleStyleSheet()

    cover_title = ParagraphStyle(
        "FullCoverTitle",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        alignment=TA_CENTER,
        spaceAfter=18,
    )
    cover_subtitle = ParagraphStyle(
        "FullCoverSubtitle",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    cover_meta = ParagraphStyle(
        "FullCoverMeta",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=6,
    )

    toc_heading = ParagraphStyle(
        "FullTocHeading",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    toc_entry = ParagraphStyle(
        "FullTocEntry",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leftIndent=18,
        bulletIndent=6,
        spaceAfter=4,
        leading=14,
    )

    index_heading = ParagraphStyle(
        "FullIndexHeading",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    index_entry = ParagraphStyle(
        "FullIndexEntry",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leftIndent=18,
        spaceAfter=4,
    )

    # Per-question styles — mirror render_preview_pdf's layout.
    header = ParagraphStyle(
        "FullHeader",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    module_line = ParagraphStyle(
        "FullModuleLine",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=11,
        spaceAfter=12,
    )
    section_label = ParagraphStyle(
        "FullSectionLabel",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        spaceBefore=10,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "FullBody",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        spaceAfter=6,
    )
    option = ParagraphStyle(
        "FullOption",
        parent=body,
        leftIndent=18,
        spaceAfter=2,
    )
    footer = ParagraphStyle(
        "FullFooter",
        parent=base["Italic"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        textColor=HexColor("#555555"),
        spaceBefore=18,
        alignment=TA_CENTER,
    )

    return {
        "cover_title": cover_title,
        "cover_subtitle": cover_subtitle,
        "cover_meta": cover_meta,
        "toc_heading": toc_heading,
        "toc_entry": toc_entry,
        "index_heading": index_heading,
        "index_entry": index_entry,
        "header": header,
        "module_line": module_line,
        "section_label": section_label,
        "body": body,
        "option": option,
        "footer": footer,
    }


def _safe_text(text: str) -> str:
    """Escape characters that reportlab's Paragraph parser treats as markup.

    Mirrors the helper in medrack.answer.render. We keep the asterisk
    convention (e.g. ``**bold**``) used by the LLM prompts.
    """
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ---------------------------------------------------------------------------
# Per-question flowable builder
# ---------------------------------------------------------------------------


def _build_question_flowables(answer, question_index, total_questions, styles):
    """Build the per-question flowables — same layout as render_preview_pdf.

    `answer` is the full answer dict from the cache (the same shape Stage
    2.4 receives: ``qid``, ``question_text``, ``question_type``, ``options``,
    ``module_name``, ``module_subject``, ``answer_text``, etc.).
    """
    flowables = []

    # Header
    header_text = f"Question {question_index} of {total_questions}"
    flowables.append(Paragraph(header_text, styles["header"]))

    # Module line
    module_name = answer.get("module_name", "")
    module_subject = answer.get("module_subject", "")
    module_line = f"Module: {module_name} ({module_subject})"
    flowables.append(Paragraph(module_line, styles["module_line"]))

    # Question section
    flowables.append(Paragraph("Question:", styles["section_label"]))
    q_text = _safe_text(answer.get("question_text", ""))
    flowables.append(Paragraph(q_text or "(no question text)", styles["body"]))
    flowables.append(Spacer(1, 6))

    # Options (if MCQ)
    qtype = answer.get("question_type") or answer.get("type")
    options = answer.get("options") or {}
    if qtype == "mcq" and options:
        for letter in sorted(options.keys()):
            line = f"\u2022 {letter}) {_safe_text(options[letter])}"
            flowables.append(Paragraph(line, styles["option"]))
        flowables.append(Spacer(1, 6))

    # Answer section
    flowables.append(Paragraph("Answer:", styles["section_label"]))
    answer_text = _safe_text(answer.get("answer_text", ""))
    flowables.append(Paragraph(answer_text or "(no answer text)", styles["body"]))

    # Footer
    footer_text = "Full module answer set."
    flowables.append(Paragraph(footer_text, styles["footer"]))

    return flowables


def _index_tag_for(answer) -> str:
    """Short tag for the index page: ``a`` for MCQ, ``theory`` otherwise."""
    qtype = answer.get("question_type") or answer.get("type")
    if qtype == "mcq":
        answer_text = (answer.get("answer_text") or "").strip()
        # The first non-empty line often starts with "ANSWER: x".
        first_line = answer_text.splitlines()[0] if answer_text else ""
        # Strip leading label, take last token's first char (the letter).
        # E.g. "ANSWER: a" -> "a", "ANSWER: b" -> "b".
        if first_line:
            last = first_line.split(":")[-1].strip()
            if last and len(last) == 1 and last.isalpha():
                return last.lower()
            if last:
                # take first character of the trimmed suffix
                return last[0].lower()
        return "?"
    return "theory"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_full_module_pdf(
    output_path,
    *,
    module_name: str,
    subject: str,
    batch_result,
    answers: list,
) -> None:
    """Render a full module PDF.

    Layout:
    - Cover page: module name (large), subject, total questions, generated date.
    - Table of contents: list of questions with placeholder page numbers.
    - Per-question pages: inline flowables (header, question, options if MCQ,
      answer, footer) — same layout as ``render_preview_pdf``.
    - Index page (last page): all question IDs and a short tag for each.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()
    story = []
    total = len(answers)

    # ---- Cover page -------------------------------------------------------
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph(_safe_text(module_name), styles["cover_title"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(f"Subject: {_safe_text(subject)}", styles["cover_subtitle"]))
    story.append(Spacer(1, 0.4 * inch))

    questions_total = getattr(batch_result, "questions_total", total)
    story.append(Paragraph(
        f"Total questions: {questions_total}",
        styles["cover_meta"],
    ))

    generated_at = datetime.now().strftime("%Y-%m-%d")
    story.append(Paragraph(f"Generated: {generated_at}", styles["cover_meta"]))

    # ---- Table of contents ------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Table of Contents", styles["toc_heading"]))
    story.append(Spacer(1, 0.2 * inch))

    # Best-effort page references: sequential numbers, 1-indexed.
    for idx, ans in enumerate(answers, start=1):
        qid = ans.get("qid", f"q{idx:03d}")
        q_text = (ans.get("question_text") or "").strip()
        snippet = q_text[:80]
        if len(q_text) > 80:
            snippet += "..."
        line = f"\u2022 {qid} \u2014 {snippet} (page ~{idx})"
        story.append(Paragraph(_safe_text(line), styles["toc_entry"]))

    # ---- Per-question pages ----------------------------------------------
    for idx, ans in enumerate(answers, start=1):
        story.append(PageBreak())
        story.extend(_build_question_flowables(ans, idx, total, styles))

    # ---- Index page -------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Index", styles["index_heading"]))
    story.append(Spacer(1, 0.2 * inch))
    for ans in answers:
        qid = ans.get("qid", "?")
        tag = _index_tag_for(ans)
        line = f"{qid} \u2192 {tag}"
        story.append(Paragraph(line, styles["index_entry"]))

    # ---- Build ------------------------------------------------------------
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
        title=f"Full module — {module_name}",
    )
    doc.build(story)
    log.info("rendered full module pdf: %s (%d questions)", output_path, total)
