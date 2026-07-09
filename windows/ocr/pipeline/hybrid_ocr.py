"""Hybrid OCR Plan C: RapidOCR full book + optional Marker table ranges."""
from __future__ import annotations

import io
import json
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image
from pypdf import PdfReader

ProgressFn = Callable[[float, str], None]

# Default Marker ranges used for Park's 27th (0-based inclusive page indices).
DEFAULT_MARKER_RANGES: List[Tuple[int, int, str]] = [
    (419, 440, "NCD_Epidemiology"),
    (503, 528, "Health_Programmes"),
    (595, 618, "RCH_PrevMed"),
    (713, 727, "Community_Care"),
    (913, 929, "Hospital_Waste"),
    (974, 987, "Biostatistics"),
    (999, 1011, "Health_Planning"),
]


def _order_rapidocr(res, width: int) -> str:
    boxes = []
    for box, txt, sc in res:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        boxes.append((min(ys), (min(xs) + max(xs)) / 2, txt))
    left = [x for x in boxes if x[1] < width * 0.48]
    right = [x for x in boxes if x[1] > width * 0.52]
    two_col = len(left) > 0.2 * len(boxes) and len(right) > 0.2 * len(boxes)
    boxes.sort(
        key=(lambda x: (0 if x[1] < width / 2 else 1, x[0]))
        if two_col
        else (lambda x: (x[0], x[1]))
    )
    return "\n".join(x[2] for x in boxes)


def _page_image(reader: PdfReader, page_index: int) -> Optional[Image.Image]:
    """Best-effort page image from embedded scan data or pypdfium2 render."""
    page = reader.pages[page_index]
    # 1) embedded images (common for scanned books)
    try:
        imgs = list(page.images)
        if imgs:
            data = max(imgs, key=lambda x: len(x.data)).data
            return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:  # noqa: BLE001
        pass
    # 2) pypdfium2 render
    try:
        import pypdfium2 as pdfium

        # PdfReader doesn't give path; caller should pass path for render path
        return None
    except Exception:  # noqa: BLE001
        return None


def _render_with_pdfium(pdf_path: Path, page_index: int, scale: float = 2.0) -> Image.Image:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf_path))
    page = doc[page_index]
    bitmap = page.render(scale=scale)
    pil = bitmap.to_pil().convert("RGB")
    doc.close()
    return pil


def rapidocr_book(
    pdf_path: Path,
    cache_dir: Path,
    *,
    progress: Optional[ProgressFn] = None,
    progress_lo: float = 5.0,
    progress_hi: float = 70.0,
) -> List[str]:
    """OCR every page with RapidOCR; resume from cache. Returns page texts (0-based)."""
    from rapidocr_onnxruntime import RapidOCR

    pdf_path = Path(pdf_path)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(pdf_path))
    n = len(reader.pages)
    ocr = RapidOCR()
    pages: List[str] = [""] * n

    for i in range(n):
        cache_file = cache_dir / f"page_{i:04d}.txt"
        if cache_file.is_file():
            pages[i] = cache_file.read_text(encoding="utf-8", errors="replace")
            if progress and (i % 25 == 0 or i == n - 1):
                frac = (i + 1) / n
                progress(progress_lo + (progress_hi - progress_lo) * frac, f"RapidOCR cache {i+1}/{n}")
            continue
        txt = ""
        try:
            im = _page_image(reader, i)
            if im is None:
                im = _render_with_pdfium(pdf_path, i)
            res, _ = ocr(np.array(im))
            txt = _order_rapidocr(res, im.size[0]) if res else ""
        except Exception as exc:  # noqa: BLE001
            txt = ""
            if progress:
                progress(
                    progress_lo + (progress_hi - progress_lo) * ((i + 1) / n),
                    f"RapidOCR page {i+1} error: {exc}",
                )
        cache_file.write_text(txt, encoding="utf-8")
        pages[i] = txt
        if progress and (i % 10 == 0 or i == n - 1):
            frac = (i + 1) / n
            progress(progress_lo + (progress_hi - progress_lo) * frac, f"RapidOCR {i+1}/{n}")

    return pages


def apply_marker_ranges(
    pdf_path: Path,
    pages: List[str],
    ranges: Sequence[Tuple[int, int, str]],
    marker_out: Path,
    *,
    progress: Optional[ProgressFn] = None,
    progress_lo: float = 70.0,
    progress_hi: float = 88.0,
) -> List[str]:
    """Optionally replace page ranges with Marker markdown (when marker works).

    If Marker fails or is unavailable, leaves RapidOCR text in place.
    """
    if not ranges:
        return pages

    marker_out = Path(marker_out)
    marker_out.mkdir(parents=True, exist_ok=True)
    out = list(pages)
    n_ranges = len(ranges)

    for ri, (start, end, name) in enumerate(ranges):
        if progress:
            frac = (ri + 0.5) / max(1, n_ranges)
            progress(
                progress_lo + (progress_hi - progress_lo) * frac,
                f"Marker {name} pages {start}-{end}",
            )
        md_path = marker_out / f"marker_{start:04d}-{end:04d}_{name}.md"
        content = ""
        if md_path.is_file():
            content = md_path.read_text(encoding="utf-8", errors="replace")
        else:
            try:
                content = _run_marker_range(pdf_path, start, end)
                md_path.write_text(content, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                if progress:
                    progress(
                        progress_lo + (progress_hi - progress_lo) * ((ri + 1) / n_ranges),
                        f"Marker skip {name}: {exc}",
                    )
                continue

        # Split Marker MD across pages in the range (same strategy as Plan C merge)
        num_pages = end - start + 1
        if num_pages <= 0:
            continue
        chunk = max(1, len(content) // num_pages)
        for i in range(num_pages):
            pidx = start + i
            if pidx < 0 or pidx >= len(out):
                continue
            a = i * chunk
            b = a + chunk if i < num_pages - 1 else len(content)
            piece = content[a:b].strip()
            if piece:
                out[pidx] = piece

        if progress:
            progress(
                progress_lo + (progress_hi - progress_lo) * ((ri + 1) / n_ranges),
                f"Marker done {name}",
            )
    return out


def _run_marker_range(pdf_path: Path, start: int, end: int) -> str:
    """Run Marker on a page range; returns markdown text.

    Uses marker-pdf converter API when available.
    """
    # Lazy import — Marker pulls torch/surya
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.config.parser import ConfigParser
        from marker.output import text_from_rendered
    except ImportError:
        # Older/alternate marker APIs
        from marker.convert import convert_single_pdf  # type: ignore

        full_text, _, _ = convert_single_pdf(str(pdf_path), max_pages=end + 1)
        # crude slice — better than nothing
        return full_text or ""

    # Build a temp PDF of just those pages for speed
    from pypdf import PdfReader, PdfWriter
    import tempfile

    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    for i in range(start, min(end + 1, len(reader.pages))):
        writer.add_page(reader.pages[i])
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        writer.write(tmp)
        tmp_path = tmp.name

    models = create_model_dict()
    converter = PdfConverter(artifact_dict=models)
    rendered = converter(tmp_path)
    text, _, _ = text_from_rendered(rendered)
    try:
        Path(tmp_path).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass
    return text or ""


def validate_ocr_pages(
    pages: Sequence[str],
    *,
    min_nonempty_ratio: float = 0.85,
    min_avg_chars: float = 40.0,
) -> Dict:
    """Quality gate before we restart Qwopus / hand PDF to MedRack."""
    n = max(1, len(pages))
    nonempty = sum(1 for p in pages if len((p or "").strip()) >= 20)
    total_chars = sum(len(p or "") for p in pages)
    avg_chars = total_chars / n
    ratio = nonempty / n
    ok = ratio >= min_nonempty_ratio and avg_chars >= min_avg_chars
    return {
        "ok": ok,
        "page_count": len(pages),
        "nonempty_pages": nonempty,
        "nonempty_ratio": round(ratio, 4),
        "avg_chars_per_page": round(avg_chars, 1),
        "min_nonempty_ratio": min_nonempty_ratio,
        "min_avg_chars": min_avg_chars,
        "message": (
            "OCR quality OK"
            if ok
            else (
                f"OCR quality failed: nonempty={ratio:.0%} "
                f"(need ≥{min_nonempty_ratio:.0%}), "
                f"avg_chars={avg_chars:.0f} (need ≥{min_avg_chars:.0f})"
            )
        ),
    }


def run_hybrid_pipeline(
    pdf_path: Path,
    work_dir: Path,
    *,
    use_marker: bool = False,
    marker_ranges: Optional[Sequence[Tuple[int, int, str]]] = None,
    progress: Optional[ProgressFn] = None,
    restart_model: bool = True,
) -> Dict:
    """Full Plan C: stop model → OCR → validate → text PDF → start model.

    Model is always restarted in ``finally`` when ``restart_model`` is True,
    even if OCR/validation fails, so answering stays available after the job.
    """
    from pipeline.build_text_pdf import build_text_only_pdf  # noqa: WPS433
    from pipeline import model_control  # noqa: WPS433

    pdf_path = Path(pdf_path)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    cache = work_dir / "rapidocr_cache"
    marker_out = work_dir / "marker_out"
    t0 = time.time()
    stop_info: Dict = {}
    start_info: Dict = {}
    pages: List[str] = []
    clean_pdf = work_dir / "clean_text.pdf"
    validation: Dict = {}

    try:
        if progress:
            progress(1, "Stopping Qwopus (free GPU for OCR)")
        stop_info = model_control.stop_model()

        if progress:
            progress(4, "Starting RapidOCR full-book pass")
        pages = rapidocr_book(
            pdf_path, cache, progress=progress, progress_lo=5, progress_hi=70
        )

        if use_marker:
            ranges = (
                list(marker_ranges)
                if marker_ranges is not None
                else list(DEFAULT_MARKER_RANGES)
            )
            pages = apply_marker_ranges(
                pdf_path,
                pages,
                ranges,
                marker_out,
                progress=progress,
                progress_lo=70,
                progress_hi=85,
            )
        elif progress:
            progress(78, "Marker skipped (use_marker=false)")

        if progress:
            progress(88, "Validating OCR quality")
        validation = validate_ocr_pages(pages)
        if not validation["ok"]:
            raise RuntimeError(validation["message"])

        if progress:
            progress(92, "Building full text PDF")
        build_text_only_pdf(pages, clean_pdf)
    finally:
        if restart_model:
            if progress:
                progress(97, "Starting Qwopus again")
            try:
                start_info = model_control.start_model()
            except Exception as exc:  # noqa: BLE001
                start_info = {"ok": False, "error": str(exc)}

    nonempty = sum(1 for p in pages if (p or "").strip())
    meta = {
        "ok": True,
        "clean_pdf": str(clean_pdf),
        "page_count": len(pages),
        "nonempty_pages": nonempty,
        "validation": validation,
        "elapsed_sec": round(time.time() - t0, 1),
        "use_marker": use_marker,
        "model_stop": stop_info,
        "model_start": start_info,
        "work_dir": str(work_dir),
    }
    (work_dir / "result.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if progress:
        progress(100, "OCR complete — model restarted")
    return meta
