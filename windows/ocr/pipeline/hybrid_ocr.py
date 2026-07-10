"""Hybrid OCR Plan C: RapidOCR full book + auto/optional Marker table ranges.

After RapidOCR, pages are scored for table-like / multi-column layout. High-
scoring pages are grouped into ranges and optionally re-OCR'd with Marker.
Works for any textbook — not limited to hardcoded Park's page numbers.
"""
from __future__ import annotations

import io
import json
import re
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image
from pypdf import PdfReader

ProgressFn = Callable[[float, str], None]

# Legacy fallback ranges (Park's 27th, 0-based inclusive). Used only when
# auto-detect finds nothing AND MEDRACK_MARKER_LEGACY_PARKS=1 is set.
DEFAULT_MARKER_RANGES: List[Tuple[int, int, str]] = [
    (419, 440, "NCD_Epidemiology"),
    (503, 528, "Health_Programmes"),
    (595, 618, "RCH_PrevMed"),
    (713, 727, "Community_Care"),
    (913, 929, "Hospital_Waste"),
    (974, 987, "Biostatistics"),
    (999, 1011, "Health_Planning"),
]

# Auto-detect caps — keep Marker jobs bounded (hours, not days).
# max fraction of book pages that may go to Marker; hard cap in pages.
AUTO_MARKER_MIN_SCORE = 0.48
AUTO_MARKER_MAX_FRACTION = 0.18
AUTO_MARKER_MAX_PAGES = 180
AUTO_MARKER_MAX_RANGE_SPAN = 28  # pages per Marker temp-PDF call
AUTO_MARKER_MERGE_GAP = 1  # merge islands within this many skipped pages


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


def score_page_for_marker(text: str) -> Dict[str, float | int | bool]:
    """Score how much a RapidOCR page looks like it needs Marker (tables/layout).

    Returns a dict with ``score`` in ``[0, 1]`` plus diagnostic fields.
    Pure text heuristics — fast, no GPU, works on any textbook language.
    """
    raw = text or ""
    stripped = raw.strip()
    if len(stripped) < 40:
        return {"score": 0.0, "lines": 0, "reason": "too_short"}

    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    n_lines = len(lines)
    if n_lines == 0:
        return {"score": 0.0, "lines": 0, "reason": "empty"}

    n_chars = sum(len(ln) for ln in lines)
    avg_line_len = n_chars / n_lines
    short_lines = sum(1 for ln in lines if len(ln) <= 28)
    short_ratio = short_lines / n_lines

    digit_chars = sum(ch.isdigit() for ch in stripped)
    alpha_chars = sum(ch.isalpha() for ch in stripped)
    digit_ratio = digit_chars / max(1, n_chars)
    alpha_ratio = alpha_chars / max(1, n_chars)

    # Multi-column / table separators in OCR text
    multi_space_lines = sum(1 for ln in lines if re.search(r"\S\s{2,}\S", ln))
    multi_space_ratio = multi_space_lines / n_lines
    pipe_lines = sum(1 for ln in lines if ln.count("|") >= 2 or ln.count("¦") >= 1)
    pipe_ratio = pipe_lines / n_lines
    # Lines that look like data rows: several tokens, many digits
    data_rowish = 0
    for ln in lines:
        toks = re.findall(r"\S+", ln)
        if len(toks) >= 4:
            dig_toks = sum(1 for t in toks if any(c.isdigit() for c in t))
            if dig_toks >= 2 and dig_toks / len(toks) >= 0.35:
                data_rowish += 1
    data_row_ratio = data_rowish / n_lines

    # Broken layout: many very short lines + decent page length → grid/table
    dense_short = 1.0 if (n_lines >= 25 and avg_line_len <= 22) else (
        0.6 if (n_lines >= 18 and avg_line_len <= 30) else 0.0
    )

    score = 0.0
    score += 0.28 * min(1.0, short_ratio / 0.55)
    score += 0.22 * min(1.0, multi_space_ratio / 0.35)
    score += 0.18 * min(1.0, data_row_ratio / 0.25)
    score += 0.12 * min(1.0, digit_ratio / 0.22)
    score += 0.10 * min(1.0, pipe_ratio / 0.15)
    score += 0.10 * dense_short
    # Penalize normal prose (long lines, high alpha, few numbers)
    if avg_line_len >= 45 and alpha_ratio >= 0.70 and digit_ratio < 0.08:
        score *= 0.35
    if alpha_ratio >= 0.78 and short_ratio < 0.25 and multi_space_ratio < 0.12:
        score *= 0.40

    score = max(0.0, min(1.0, score))
    return {
        "score": round(score, 4),
        "lines": n_lines,
        "avg_line_len": round(avg_line_len, 1),
        "short_ratio": round(short_ratio, 3),
        "digit_ratio": round(digit_ratio, 3),
        "multi_space_ratio": round(multi_space_ratio, 3),
        "data_row_ratio": round(data_row_ratio, 3),
        "needs_marker": score >= AUTO_MARKER_MIN_SCORE,
    }


def detect_marker_page_indices(
    pages: Sequence[str],
    *,
    min_score: float = AUTO_MARKER_MIN_SCORE,
    max_fraction: float = AUTO_MARKER_MAX_FRACTION,
    max_pages: int = AUTO_MARKER_MAX_PAGES,
) -> Tuple[List[int], List[Dict]]:
    """Return 0-based page indices that should go through Marker.

    Caps selection so a false-positive heuristic cannot send the whole book
    to Marker (which would take many hours).
    """
    scored: List[Tuple[float, int, Dict]] = []
    details: List[Dict] = []
    for i, text in enumerate(pages):
        info = score_page_for_marker(text or "")
        info = dict(info)
        info["page"] = i  # 0-based
        info["page_1based"] = i + 1
        details.append(info)
        if float(info.get("score") or 0) >= min_score:
            scored.append((float(info["score"]), i, info))

    # Highest scores first when we must cap
    scored.sort(key=lambda x: (-x[0], x[1]))
    n = max(1, len(pages))
    budget = min(max_pages, max(1, int(n * max_fraction)))
    chosen = sorted(idx for _, idx, _ in scored[:budget])
    return chosen, details


def group_indices_to_ranges(
    indices: Sequence[int],
    *,
    merge_gap: int = AUTO_MARKER_MERGE_GAP,
    max_span: int = AUTO_MARKER_MAX_RANGE_SPAN,
) -> List[Tuple[int, int, str]]:
    """Merge nearby page indices into Marker ranges ``(start, end, name)``."""
    if not indices:
        return []
    sorted_idx = sorted(set(int(i) for i in indices if i >= 0))
    ranges: List[Tuple[int, int, str]] = []
    start = sorted_idx[0]
    prev = sorted_idx[0]
    for idx in sorted_idx[1:]:
        # Close enough to merge, and span would stay within max_span
        if idx - prev <= merge_gap + 1 and (idx - start) < max_span:
            prev = idx
            continue
        ranges.append((start, prev, f"auto_{start:04d}_{prev:04d}"))
        start = idx
        prev = idx
    ranges.append((start, prev, f"auto_{start:04d}_{prev:04d}"))
    return ranges


def select_marker_ranges(
    pages: Sequence[str],
    *,
    explicit_ranges: Optional[Sequence[Tuple[int, int, str]]] = None,
    auto: bool = True,
    min_score: float = AUTO_MARKER_MIN_SCORE,
) -> Tuple[List[Tuple[int, int, str]], Dict]:
    """Choose Marker ranges for this book.

    Priority:
    1. ``explicit_ranges`` if provided (tests / manual override)
    2. Auto-detect from RapidOCR text (default for any textbook)
    3. Optional legacy Park's ranges if env ``MEDRACK_MARKER_LEGACY_PARKS=1``
       and auto found nothing
    """
    import os

    report: Dict = {
        "mode": "none",
        "selected_pages": 0,
        "ranges": [],
        "min_score": min_score,
        "capped": False,
    }
    if explicit_ranges is not None:
        ranges = list(explicit_ranges)
        report["mode"] = "explicit"
        report["selected_pages"] = sum(max(0, e - s + 1) for s, e, _ in ranges)
        report["ranges"] = [{"start": s, "end": e, "name": n} for s, e, n in ranges]
        return ranges, report

    if not auto:
        report["mode"] = "disabled"
        return [], report

    indices, details = detect_marker_page_indices(pages, min_score=min_score)
    n = max(1, len(pages))
    budget = min(AUTO_MARKER_MAX_PAGES, max(1, int(n * AUTO_MARKER_MAX_FRACTION)))
    high = sum(1 for d in details if float(d.get("score") or 0) >= min_score)
    report["capped"] = high > budget
    report["candidates"] = high
    report["top_scores"] = sorted(
        (
            {"page_1based": d["page_1based"], "score": d["score"]}
            for d in details
            if float(d.get("score") or 0) >= min_score
        ),
        key=lambda x: -float(x["score"]),
    )[:40]

    ranges = group_indices_to_ranges(indices)
    if ranges:
        report["mode"] = "auto"
        report["selected_pages"] = len(indices)
        report["ranges"] = [{"start": s, "end": e, "name": n} for s, e, n in ranges]
        return ranges, report

    if os.environ.get("MEDRACK_MARKER_LEGACY_PARKS", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        report["mode"] = "legacy_parks"
        ranges = list(DEFAULT_MARKER_RANGES)
        report["selected_pages"] = sum(max(0, e - s + 1) for s, e, _ in ranges)
        report["ranges"] = [{"start": s, "end": e, "name": n} for s, e, n in ranges]
        return ranges, report

    report["mode"] = "auto_none"
    return [], report


def _distribute_marker_text(
    content: str,
    start: int,
    end: int,
    rapid_pages: Sequence[str],
) -> List[Tuple[int, str]]:
    """Map Marker markdown onto page indices without crude equal char-split.

    Priority:
    1. Explicit page breaks (form-feed / markers) when count matches
    2. Proportional weights from RapidOCR page lengths + paragraph-aware cuts
    3. Equal-ish fallback with newline-aware cuts (never mid-word when possible)
    """
    content = (content or "").strip()
    num_pages = end - start + 1
    if not content or num_pages <= 0:
        return []
    if num_pages == 1:
        return [(start, content)]

    # Explicit page separators (some converters emit these)
    for sep in ("\f", "\n\x0c", "\n---PAGE---\n", "\n<!-- page -->\n", "\n\n---\n\n"):
        if sep in content:
            parts = [p.strip() for p in content.split(sep)]
            # Drop empty leading/trailing from split artifacts
            while parts and not parts[0]:
                parts.pop(0)
            while parts and not parts[-1]:
                parts.pop()
            if len(parts) == num_pages:
                return [
                    (start + i, parts[i])
                    for i in range(num_pages)
                    if parts[i]
                ]

    # Weights from RapidOCR page text lengths (preserve relative bulk)
    weights: List[int] = []
    for i in range(num_pages):
        pidx = start + i
        raw = rapid_pages[pidx] if 0 <= pidx < len(rapid_pages) else ""
        weights.append(max(len(raw or ""), 80))

    total_w = sum(weights) or num_pages
    n = len(content)
    targets = [max(40, int(round(n * w / total_w))) for w in weights]
    # Fix rounding so targets sum to n
    drift = n - sum(targets)
    if targets:
        targets[-1] = max(1, targets[-1] + drift)

    pieces: List[str] = []
    pos = 0
    for i in range(num_pages):
        if i == num_pages - 1:
            pieces.append(content[pos:].strip())
            break
        target_end = min(n, pos + targets[i])
        # Prefer paragraph, then line, then space break near target
        break_at = target_end
        search_lo = max(pos + 20, target_end - 120)
        search_hi = min(n, target_end + 160)
        window = content[search_lo:search_hi]
        for pat in ("\n\n", "\n", " "):
            # find break closest to target_end within window
            rel = target_end - search_lo
            best = None
            best_dist = 10**9
            idx = 0
            while True:
                j = window.find(pat, idx)
                if j < 0:
                    break
                abs_pos = search_lo + j + len(pat)
                dist = abs(abs_pos - target_end)
                if dist < best_dist and abs_pos > pos:
                    best_dist = dist
                    best = abs_pos
                idx = j + 1
            if best is not None:
                break_at = best
                break
        if break_at <= pos:
            break_at = min(n, pos + max(1, targets[i]))
        pieces.append(content[pos:break_at].strip())
        pos = break_at

    out: List[Tuple[int, str]] = []
    for i, piece in enumerate(pieces):
        if piece:
            out.append((start + i, piece))
    return out


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
    Multi-page Marker output is distributed with paragraph-aware proportional
    split (not equal char-split), weighted by RapidOCR page lengths.
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
                f"Marker {name} pages {start + 1}-{end + 1}",
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

        num_pages = end - start + 1
        if num_pages <= 0:
            continue
        for pidx, piece in _distribute_marker_text(content, start, end, out):
            if 0 <= pidx < len(out) and piece:
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


def _page_gibberish_score(text: str) -> float:
    """0..1 gibberish heuristic (1 = unusable OCR noise)."""
    if not text or not text.strip():
        return 1.0
    raw = text.strip()
    n = len(raw)
    if n < 20:
        return 0.85
    alpha = sum(ch.isalpha() for ch in raw)
    digit = sum(ch.isdigit() for ch in raw)
    alpha_ratio = alpha / n
    vowels = sum(ch.lower() in "aeiou" for ch in raw if ch.isalpha())
    vowel_ratio = vowels / max(1, alpha)
    weird = sum(
        1
        for ch in raw
        if not (ch.isalnum() or ch.isspace() or ch in ".,;:()[]-%/'\"")
    )
    weird_ratio = weird / n
    words = [w for w in raw.split() if w]
    avg_w = (sum(len(w) for w in words) / len(words)) if words else 0.0
    # Fraction of tokens that look like real words (letters only, length 3+)
    realish = sum(1 for w in words if len(w) >= 3 and w.isalpha()) / max(1, len(words))

    score = 0.0
    if alpha_ratio < 0.30:
        score += 0.55
    elif alpha_ratio < 0.45:
        score += 0.40
    elif alpha_ratio < 0.55:
        score += 0.18
    if alpha > 20 and vowel_ratio < 0.22:
        score += 0.25
    if weird_ratio > 0.25:
        score += 0.35
    elif weird_ratio > 0.12:
        score += 0.22
    if avg_w > 0 and (avg_w < 2.2 or avg_w > 18):
        score += 0.15
    if realish < 0.25 and n > 40:
        score += 0.25
    if digit / n > 0.45 and alpha_ratio < 0.3:
        score += 0.1
    return max(0.0, min(1.0, score))


def validate_ocr_pages(
    pages: Sequence[str],
    *,
    min_nonempty_ratio: float = 0.85,
    min_avg_chars: float = 40.0,
    max_mean_gibberish: float = 0.78,
) -> Dict:
    """Quality gate before we restart Qwopus / hand PDF to MedRack.

    Checks nonempty ratio, avg chars, and a gibberish score on sample pages
    so garbage OCR does not silently become a textbook KB.
    """
    n = max(1, len(pages))
    nonempty = sum(1 for p in pages if len((p or "").strip()) >= 20)
    total_chars = sum(len(p or "") for p in pages)
    avg_chars = total_chars / n
    ratio = nonempty / n

    # Sample evenly across the book for gibberish
    sample_idx = list(range(0, len(pages), max(1, len(pages) // 12)))[:12]
    if not sample_idx and pages:
        sample_idx = [0]
    gib_scores = [
        _page_gibberish_score(pages[i] or "")
        for i in sample_idx
        if 0 <= i < len(pages)
    ]
    mean_gib = (sum(gib_scores) / len(gib_scores)) if gib_scores else 1.0
    max_gib = max(gib_scores) if gib_scores else 1.0

    structure_ok = ratio >= min_nonempty_ratio and avg_chars >= min_avg_chars
    gib_ok = mean_gib < max_mean_gibberish
    ok = structure_ok and gib_ok

    if ok:
        message = "OCR quality OK"
    elif not structure_ok:
        message = (
            f"OCR quality failed: nonempty={ratio:.0%} "
            f"(need >={min_nonempty_ratio:.0%}), "
            f"avg_chars={avg_chars:.0f} (need >={min_avg_chars:.0f})"
        )
    else:
        message = (
            f"OCR quality failed: mean_gibberish={mean_gib:.3f} "
            f"(need < {max_mean_gibberish})"
        )

    return {
        "ok": ok,
        "page_count": len(pages),
        "nonempty_pages": nonempty,
        "nonempty_ratio": round(ratio, 4),
        "avg_chars_per_page": round(avg_chars, 1),
        "min_nonempty_ratio": min_nonempty_ratio,
        "min_avg_chars": min_avg_chars,
        "mean_gibberish": round(mean_gib, 3),
        "max_gibberish": round(max_gib, 3),
        "max_mean_gibberish": max_mean_gibberish,
        "gibberish_samples": len(gib_scores),
        "message": message,
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
    marker_report: Dict = {"mode": "disabled", "selected_pages": 0, "ranges": []}
    ranges_used: List[Tuple[int, int, str]] = []

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
            if progress:
                progress(70.5, "Scoring pages for tables / multi-column layout…")
            ranges_used, marker_report = select_marker_ranges(
                pages,
                explicit_ranges=marker_ranges,
                auto=True,
            )
            n_sel = int(marker_report.get("selected_pages") or 0)
            if ranges_used:
                if progress:
                    progress(
                        71,
                        f"Auto Marker: {n_sel} page(s) in {len(ranges_used)} range(s) "
                        f"({marker_report.get('mode')})",
                    )
                pages = apply_marker_ranges(
                    pdf_path,
                    pages,
                    ranges_used,
                    marker_out,
                    progress=progress,
                    progress_lo=71,
                    progress_hi=86,
                )
            elif progress:
                progress(
                    78,
                    "Marker: no table-heavy pages detected — RapidOCR only",
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
        "marker": marker_report if use_marker else {"mode": "disabled"},
        "marker_ranges": [
            {"start": s, "end": e, "name": n, "pages_1based": f"{s + 1}-{e + 1}"}
            for s, e, n in (ranges_used if use_marker else [])
        ],
        "model_stop": stop_info,
        "model_start": start_info,
        "work_dir": str(work_dir),
    }
    (work_dir / "result.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if progress:
        progress(100, "OCR complete — model restarted")
    return meta
