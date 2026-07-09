"""Unit tests for auto Marker page selection (no GPU / Marker install required)."""
from __future__ import annotations

from pipeline.hybrid_ocr import (
    group_indices_to_ranges,
    score_page_for_marker,
    select_marker_ranges,
)


def test_prose_scores_low():
    prose = "\n".join(
        [
            "Maternal health is a cornerstone of primary care. Antenatal visits "
            "should include history, examination, and counselling for the family.",
            "The community health worker coordinates with the primary health centre "
            "to ensure follow-up and referral when danger signs appear during pregnancy.",
            "National programmes support iron supplementation, tetanus immunization, "
            "and institutional delivery with free transport under JSSK where available.",
        ]
        * 4
    )
    s = score_page_for_marker(prose)
    assert float(s["score"]) < 0.48, s


def test_tableish_scores_high():
    # Simulated broken OCR of a multi-column stats table
    rows = []
    for i in range(30):
        rows.append(f"Row{i}   12.4   45.6   78   Yes   3.2")
        rows.append(f"Item {i}  9  11  13  15")
    table = "\n".join(rows)
    s = score_page_for_marker(table)
    assert float(s["score"]) >= 0.48, s
    assert s["needs_marker"] is True


def test_group_ranges_merges_and_splits():
    idx = [10, 11, 12, 20, 50, 51]
    ranges = group_indices_to_ranges(idx, merge_gap=1, max_span=28)
    assert (10, 12, "auto_0010_0012") in ranges
    assert any(r[0] == 20 and r[1] == 20 for r in ranges)
    assert (50, 51, "auto_0050_0051") in ranges


def test_select_auto_on_mixed_book():
    pages = []
    prose = "Normal textbook prose about epidemiology and prevention of disease. " * 20
    table = "\n".join(f"A  {i}  {i*2}  {i*3}  B" for i in range(40))
    for i in range(20):
        pages.append(prose if i not in (5, 6, 7, 15) else table)
    ranges, report = select_marker_ranges(pages, auto=True)
    assert report["mode"] == "auto"
    assert report["selected_pages"] >= 3
    assert ranges
    # pages 5-7 should be covered
    covered = set()
    for s, e, _ in ranges:
        for p in range(s, e + 1):
            covered.add(p)
    assert 5 in covered and 6 in covered and 7 in covered


if __name__ == "__main__":
    test_prose_scores_low()
    test_tableish_scores_high()
    test_group_ranges_merges_and_splits()
    test_select_auto_on_mixed_book()
    print("all ok")
