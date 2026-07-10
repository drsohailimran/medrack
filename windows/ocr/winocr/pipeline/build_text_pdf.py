"""Build a full text-layer (or text-only) PDF from per-page OCR strings.

Unlike the earlier merge_and_wrap.py (which truncated to 50 lines × 80 chars),
this writer emits **all** page text so MedRack text_extract sees a complete
text layer and skips Tesseract.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def _wrap_lines(text: str, max_chars: int = 100) -> List[str]:
    lines: List[str] = []
    for raw in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        raw = raw.rstrip()
        if not raw:
            lines.append("")
            continue
        while len(raw) > max_chars:
            cut = raw.rfind(" ", 0, max_chars)
            if cut < max_chars // 2:
                cut = max_chars
            lines.append(raw[:cut])
            raw = raw[cut:].lstrip()
        lines.append(raw)
    return lines


def build_text_only_pdf(
    page_texts: Sequence[str],
    out_path: Union[str, Path],
    *,
    font_size: float = 9.0,
    leading: float = 11.0,
) -> Path:
    """One PDF page per OCR page; full text, no truncation.

    Multi-page continuation: if a page's text does not fit, overflow creates
    extra PDF pages labeled with the source page index (MedRack still gets
    all characters into the extract → clean → chunk path).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    packet = io.BytesIO()
    c = canvas.Canvas(str(out_path), pagesize=letter)
    width, height = letter
    margin = 40
    usable_h = height - 2 * margin
    lines_per_page = max(1, int(usable_h / leading))

    for i, text in enumerate(page_texts):
        lines = _wrap_lines(text or "", max_chars=95)
        if not lines:
            lines = [f"[page {i + 1}: no OCR text]"]
        # Header
        header = f"--- source page {i + 1} ---"
        chunks: List[List[str]] = []
        buf = [header]
        for ln in lines:
            if len(buf) >= lines_per_page:
                chunks.append(buf)
                buf = [f"--- source page {i + 1} (cont.) ---"]
            buf.append(ln)
        if buf:
            chunks.append(buf)

        for part in chunks:
            y = height - margin
            c.setFont("Helvetica", font_size)
            c.setFillColorRGB(0, 0, 0)
            for ln in part:
                # ReportLab needs latin-1-safe-ish; replace non-encodable
                safe = ln.encode("latin-1", errors="replace").decode("latin-1")
                c.drawString(margin, y, safe[:120])
                y -= leading
            c.showPage()

    c.save()
    return out_path


def build_overlay_pdf(
    source_pdf: Union[str, Path],
    page_texts: Sequence[str],
    out_path: Union[str, Path],
    *,
    font_size: float = 6.0,
) -> Path:
    """Merge full invisible text onto scanned pages (no 50-line cap)."""
    source_pdf = Path(source_pdf)
    out_path = Path(out_path)
    reader = PdfReader(str(source_pdf))
    writer = PdfWriter()
    n = len(reader.pages)

    for page_num in range(n):
        original = reader.pages[page_num]
        text = page_texts[page_num] if page_num < len(page_texts) else ""
        if text.strip():
            # Use actual page size when possible
            try:
                w = float(original.mediabox.width)
                h = float(original.mediabox.height)
            except Exception:  # noqa: BLE001
                w, h = letter

            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(w, h))
            c.setFillColorRGB(1, 1, 1)  # invisible / near-white
            c.setFont("Helvetica", font_size)
            leading = font_size + 1.5
            y = h - 20
            for ln in _wrap_lines(text, max_chars=int(w / (font_size * 0.5))):
                if y < 10:
                    # Continue from top again (overlap OK for extractors)
                    y = h - 20
                safe = ln.encode("latin-1", errors="replace").decode("latin-1")
                c.drawString(12, y, safe[:200])
                y -= leading
            c.save()
            buf.seek(0)
            overlay = PdfReader(buf).pages[0]
            original.merge_page(overlay)
        writer.add_page(original)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        writer.write(f)
    return out_path
