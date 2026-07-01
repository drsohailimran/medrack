"""Render a beautiful full-module answer PDF.

Styled after the "Exam-Prep Answer Bank" reference: a navy cover with a
Contents list, a running header + footer on every content page, each question
in a navy banner box (white bold text), blue section headings, justified
point-form answers with bold lead-ins, and questions flowing continuously
(no page break per question — just a small gap between them).
"""
import re
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from medrack.answer.render import (
    _split_answer_blocks,
    _make_table_flowable,
    _make_diagram_flowable,
    _safe_text as _rich_safe_text,
    clean_answer_text,
)
from medrack.utils.logger import get_logger

log = get_logger(__name__)

# Palette (matches the reference).
NAVY = HexColor("#1a3a6c")
BLUE = HexColor("#2b5aa0")
GRAY = HexColor("#555555")
LIGHTGRAY = HexColor("#888888")
RULE_LIGHT = HexColor("#c9c9c9")

_SUBJECT_DISPLAY = {
    "psm": "COMMUNITY MEDICINE",
    "fmt": "FORENSIC MEDICINE",
    "medicine": "GENERAL MEDICINE",
    "surgery": "GENERAL SURGERY",
    "obgyn": "OBSTETRICS & GYNAECOLOGY",
    "pediatrics": "PAEDIATRICS",
    "ortho": "ORTHOPAEDICS",
    "ent": "ENT",
    "ophthalmology": "OPHTHALMOLOGY",
}


def _subject_display(subject: str) -> str:
    return _SUBJECT_DISPLAY.get((subject or "").lower(), (subject or "").upper() or "EXAM ANSWERS")


def _build_styles():
    base = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    return {
        "cover_title": S(
            "cover_title", fontName="Helvetica-Bold", fontSize=26, leading=32,
            alignment=TA_CENTER, textColor=NAVY, spaceAfter=6,
        ),
        "cover_sub": S(
            "cover_sub", fontName="Helvetica", fontSize=13, leading=18,
            alignment=TA_CENTER, textColor=BLUE, spaceAfter=4,
        ),
        "cover_note": S(
            "cover_note", fontName="Helvetica-Oblique", fontSize=9.5, leading=13,
            alignment=TA_CENTER, textColor=GRAY,
        ),
        "contents_h": S(
            "contents_h", fontName="Helvetica-Bold", fontSize=13, textColor=NAVY,
            spaceBefore=6, spaceAfter=4,
        ),
        "contents_item": S(
            "contents_item", fontName="Helvetica", fontSize=10.5, leading=15,
            leftIndent=12, firstLineIndent=-12, textColor=HexColor("#222222"),
            spaceAfter=1,
        ),
        # The navy question banner (white bold text on a filled box).
        "qbox": S(
            "qbox", fontName="Helvetica-Bold", fontSize=11.5, leading=15,
            textColor=colors.white, backColor=NAVY, borderPadding=(8, 10, 8, 10),
            spaceBefore=20, spaceAfter=10,
        ),
        "ans_heading": S(
            "ans_heading", fontName="Helvetica-Bold", fontSize=11, leading=14,
            textColor=NAVY, spaceBefore=9, spaceAfter=3,
        ),
        "body": S(
            "body", fontName="Helvetica", fontSize=10.5, leading=15,
            alignment=TA_JUSTIFY, spaceAfter=4,
        ),
        "bullet": S(
            "bullet", fontName="Helvetica", fontSize=10.5, leading=15,
            alignment=TA_JUSTIFY, leftIndent=18, firstLineIndent=-12, spaceBefore=1,
            spaceAfter=4,
        ),
        "sub_bullet": S(
            "sub_bullet", fontName="Helvetica", fontSize=10, leading=14,
            alignment=TA_JUSTIFY, leftIndent=34, firstLineIndent=-12, spaceBefore=1,
            spaceAfter=3,
        ),
        "option": S(
            "option", fontName="Helvetica", fontSize=10.5, leading=14,
            leftIndent=20, spaceAfter=2,
        ),
    }


def _answer_flowables(answer_text: str, styles) -> list:
    """Turn the LLM answer into styled flowables (headings, bullets, paras)."""
    out = []
    for kind, content in _split_answer_blocks(answer_text):
        if kind == "main_bullet":
            out.append(Paragraph("•  " + _rich_safe_text(content), styles["bullet"]))
        elif kind == "sub_bullet":
            out.append(Paragraph("–  " + _rich_safe_text(content), styles["sub_bullet"]))
        elif kind == "heading":
            head = re.sub(r"\s*[:\-]+\s*$", "", content).strip()
            if head:
                out.append(Paragraph(_rich_safe_text(head), styles["ans_heading"]))
        elif kind == "table":
            tbl = _make_table_flowable(content, A4[0] - 2 * inch)
            if tbl is not None:
                out.append(Spacer(1, 3))
                out.append(tbl)
                out.append(Spacer(1, 6))
        elif kind == "diagram":
            img = _make_diagram_flowable(content, A4[0] - 2 * inch)
            if img is not None:
                out.append(Spacer(1, 4))
                out.append(img)
                out.append(Spacer(1, 6))
        else:
            out.append(Paragraph(_rich_safe_text(content), styles["body"]))
    return out


def _build_question_flowables(answer, idx, styles) -> list:
    """Question banner + its answer body."""
    flow = []
    qtext = _rich_safe_text(answer.get("question_text", "") or "(no question text)")
    marks = answer.get("marks")
    mtag = f"  ({marks} marks)" if marks in (5, 10) else ""
    flow.append(Paragraph(f"Q{idx}. {qtext}{mtag}", styles["qbox"]))

    qtype = answer.get("question_type") or answer.get("type")
    options = answer.get("options") or {}
    if qtype == "mcq" and options:
        for letter in sorted(options.keys()):
            flow.append(
                Paragraph(f"({letter}) {_rich_safe_text(options[letter])}", styles["option"])
            )

    ans = clean_answer_text(answer.get("answer_text", "") or "")
    if ans.strip():
        flow.extend(_answer_flowables(ans, styles))
    else:
        flow.append(Paragraph("(no answer generated)", styles["body"]))
    return flow


def render_full_module_pdf(
    output_path,
    *,
    module_name: str,
    subject: str,
    batch_result,
    answers: list,
) -> None:
    """Render the styled full-module answer PDF (see module docstring)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()
    disp = _subject_display(subject)
    total = len(answers)
    story: list = []

    # ---- Cover page -------------------------------------------------------
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph("Exam-Prep Answer Bank", styles["cover_title"]))
    story.append(
        HRFlowable(width="38%", thickness=1.3, color=NAVY, spaceBefore=6, spaceAfter=14, hAlign="CENTER")
    )
    story.append(Paragraph(disp.title(), styles["cover_sub"]))
    story.append(
        Paragraph(
            f"{_rich_safe_text(module_name)}  •  {subject.upper()}  •  "
            f"{total} question{'s' if total != 1 else ''}",
            styles["cover_sub"],
        )
    )
    story.append(Spacer(1, 0.55 * inch))

    story.append(Paragraph("Contents", styles["contents_h"]))
    story.append(HRFlowable(width="100%", thickness=0.6, color=RULE_LIGHT, spaceBefore=1, spaceAfter=8))
    for idx, ans in enumerate(answers, start=1):
        q = (ans.get("question_text") or "").strip()
        snip = q[:92] + ("…" if len(q) > 92 else "")
        mk = ans.get("marks")
        mtag = f" <font color='#888888'>({mk} marks)</font>" if mk in (5, 10) else ""
        story.append(
            Paragraph(f"<b>Q{idx}.</b> {_rich_safe_text(snip)}{mtag}", styles["contents_item"])
        )

    story.append(Spacer(1, 0.45 * inch))
    story.append(
        Paragraph(
            "Answers are in point form for direct use in the answer booklet, written at the "
            "length expected for the marks.<br/>Verify frequently-revised Indian data against "
            "your current edition before the exam.",
            styles["cover_note"],
        )
    )
    story.append(PageBreak())

    # ---- Questions (continuous flow, small gap between each) --------------
    for idx, ans in enumerate(answers, start=1):
        qflow = _build_question_flowables(ans, idx, styles)
        # Keep the banner with its first couple of lines so it never orphans
        # at the very bottom of a page.
        head, rest = qflow[:3], qflow[3:]
        story.append(KeepTogether(head))
        story.extend(rest)

    # ---- Running header + footer -----------------------------------------
    def _decorate(canv, _doc):
        page = canv.getPageNumber()
        w, h = A4
        canv.saveState()
        if page > 1:
            canv.setFont("Helvetica-Bold", 8.5)
            canv.setFillColor(NAVY)
            canv.drawString(1 * inch, h - 0.6 * inch, disp)
            canv.setFont("Helvetica", 8.5)
            canv.setFillColor(GRAY)
            canv.drawRightString(w - 1 * inch, h - 0.6 * inch, module_name[:60])
            canv.setStrokeColor(NAVY)
            canv.setLineWidth(0.6)
            canv.line(1 * inch, h - 0.68 * inch, w - 1 * inch, h - 0.68 * inch)
        canv.setStrokeColor(RULE_LIGHT)
        canv.setLineWidth(0.5)
        canv.line(1 * inch, 0.72 * inch, w - 1 * inch, 0.72 * inch)
        canv.setFont("Helvetica-Oblique", 8)
        canv.setFillColor(LIGHTGRAY)
        canv.drawString(
            1 * inch,
            0.55 * inch,
            "Exam-prep study notes — write in your own hand. Verify current Indian data against your edition.",
        )
        canv.setFont("Helvetica", 8)
        canv.drawRightString(w - 1 * inch, 0.55 * inch, f"Page {page}")
        canv.restoreState()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=0.95 * inch,
        bottomMargin=0.9 * inch,
        title=f"{module_name} — solved answers",
    )
    doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
    log.info("rendered full module pdf: %s (%d questions)", output_path, total)
