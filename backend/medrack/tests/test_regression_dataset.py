"""Tests for the permanent regression dataset (Phase 4, directive v1.0).

These tests validate the dataset's structure and integrity — they do
not run the regression itself (that lands in Phase 5 with the
benchmark framework). The tests here are the dataset's *contract*:
they make sure future changes don't accidentally corrupt the
benchmark set.
"""
import json
from pathlib import Path

import pytest

from medrack.tests.regression_datasets import (
    load_regression_dataset,
    get_regression_questions,
    list_available_versions,
    ACTIVE_VERSION,
)


# ---------------------------------------------------------------------------
# Dataset structure
# ---------------------------------------------------------------------------


def test_dataset_v1_loads():
    ds = load_regression_dataset(1)
    assert ds["_version"] == 1
    assert "questions" in ds
    assert len(ds["questions"]) == 20


def test_active_version_is_1():
    assert ACTIVE_VERSION == 1


def test_v1_in_list_of_available_versions():
    assert 1 in list_available_versions()


def test_dataset_has_required_metadata_fields():
    ds = load_regression_dataset(1)
    for field in ("_doc", "_version", "_created", "_module_sources", "questions"):
        assert field in ds, f"missing metadata field: {field}"


def test_dataset_metadata_doc_mentions_never_modify():
    """The _doc field must contain the 'NEVER MODIFY' warning."""
    ds = load_regression_dataset(1)
    assert "NEVER MODIFY" in ds["_doc"]


def test_dataset_module_sources_point_to_real_files():
    """_module_sources paths should exist (the source extracted.json files)."""
    ds = load_regression_dataset(1)
    medrack_root = Path(__file__).resolve().parents[2]  # tests/test_regression_dataset.py -> medrack/
    for module, rel_path in ds["_module_sources"].items():
        abs_path = medrack_root / rel_path
        assert abs_path.exists(), f"module source {abs_path} for {module!r} does not exist"


# ---------------------------------------------------------------------------
# Question coverage (the directive's mix)
# ---------------------------------------------------------------------------


def test_dataset_has_20_questions():
    qs = get_regression_questions()
    assert len(qs) == 20


def test_dataset_covers_psm_and_fmt():
    qs = get_regression_questions()
    subjects = {q["subject"] for q in qs}
    assert subjects == {"psm", "fmt"}, f"expected psm+fmt, got {subjects}"


def test_dataset_has_5_mark_and_10_mark_questions():
    qs = get_regression_questions()
    marks = {q["marks"] for q in qs}
    assert marks == {5, 10}, f"expected 5+10, got {marks}"


def test_dataset_covers_easy_moderate_difficult():
    qs = get_regression_questions()
    difficulties = {q["difficulty"] for q in qs}
    assert difficulties == {"easy", "moderate", "difficult"}, (
        f"expected all three difficulty levels, got {difficulties}"
    )


def test_dataset_has_mix_of_long_and_short_questions():
    """5-mark = short, 10-mark = long; dataset should have both."""
    qs = get_regression_questions()
    n_5 = sum(1 for q in qs if q["marks"] == 5)
    n_10 = sum(1 for q in qs if q["marks"] == 10)
    assert n_5 > 0 and n_10 > 0, f"5-mark={n_5}, 10-mark={n_10}"
    # 5-mark and 10-mark both should be reasonably represented
    assert n_10 >= 8, f"too few 10-mark questions: {n_10} (expected ≥8 for a representative long-answer benchmark)"


def test_dataset_has_at_least_8_psm_and_at_least_8_fmt():
    """Both subjects should be well-represented."""
    qs = get_regression_questions()
    n_psm = sum(1 for q in qs if q["subject"] == "psm")
    n_fmt = sum(1 for q in qs if q["subject"] == "fmt")
    assert n_psm >= 8, f"too few PSM questions: {n_psm}"
    assert n_fmt >= 8, f"too few FMT questions: {n_fmt}"


def test_dataset_qids_are_unique_within_module():
    """Within a module, qids should be unique (q173 can appear in both
    PSM and FMT, but not twice in the same module)."""
    qs = get_regression_questions()
    seen = set()
    for q in qs:
        key = (q["module"], q["qid"])
        assert key not in seen, f"duplicate (module, qid): {key}"
        seen.add(key)


# ---------------------------------------------------------------------------
# Question text validation (every question should exist in the source module)
# ---------------------------------------------------------------------------


def test_all_qids_exist_in_source_modules():
    """Every (module, qid) in the dataset should be a theory question
    in the corresponding module's extracted.json."""
    ds = load_regression_dataset(1)
    medrack_root = Path(__file__).resolve().parents[2]

    for q in ds["questions"]:
        module = q["module"]
        qid = q["qid"]
        extracted_path = medrack_root / ds["_module_sources"][module]
        extracted = json.loads(extracted_path.read_text())
        ids = {item["qid"]: item for item in extracted["questions"]}
        assert qid in ids, (
            f"qid {qid!r} not in {extracted_path} (module {module!r})"
        )
        item = ids[qid]
        assert item["type"] == "theory", (
            f"{module}/{qid} is type={item['type']!r}, expected 'theory'"
        )


def test_all_qids_match_their_declared_marks():
    """The marks field on the dataset entry should match the marks on
    the source question (or None if the source has no detected marks
    — the dataset should still declare an effective marks value for
    prompt sizing)."""
    ds = load_regression_dataset(1)
    medrack_root = Path(__file__).resolve().parents[2]

    for q in ds["questions"]:
        module = q["module"]
        qid = q["qid"]
        extracted_path = medrack_root / ds["_module_sources"][module]
        extracted = json.loads(extracted_path.read_text())
        ids = {item["qid"]: item for item in extracted["questions"]}
        src_marks = ids[qid].get("marks")
        # The dataset always declares marks in {5, 10} (we picked them
        # to be exam-relevant). The source's marks may be None if the
        # OCR-garbling was too severe — that's a data-quality issue,
        # not a dataset problem.
        if src_marks is not None:
            assert q["marks"] == src_marks, (
                f"{module}/{qid}: dataset says marks={q['marks']} but "
                f"source says {src_marks}"
            )


def test_all_qids_have_a_section_field():
    qs = get_regression_questions()
    for q in qs:
        assert "section" in q and q["section"], (
            f"{q['module']}/{q['qid']} missing section"
        )
        assert isinstance(q["section"], str)


# ---------------------------------------------------------------------------
# Loader behaviour
# ---------------------------------------------------------------------------


def test_load_missing_version_raises():
    with pytest.raises(FileNotFoundError):
        load_regression_dataset(999)


def test_loader_returns_fresh_dict_each_call():
    """Loaders should return new dicts (caller can mutate safely)."""
    ds1 = load_regression_dataset(1)
    ds2 = load_regression_dataset(1)
    assert ds1 is not ds2
    ds1["questions"].append({"bogus": True})
    assert len(ds2["questions"]) == 20  # not contaminated


def test_get_regression_questions_returns_questions_list():
    qs = get_regression_questions()
    assert isinstance(qs, list)
    assert all(isinstance(q, dict) for q in qs)


# ---------------------------------------------------------------------------
# Question schema (each entry should have the required fields)
# ---------------------------------------------------------------------------


REQUIRED_FIELDS = {"module", "qid", "subject", "marks", "section", "difficulty", "topic", "notes"}


def test_every_question_has_required_fields():
    qs = get_regression_questions()
    for q in qs:
        missing = REQUIRED_FIELDS - set(q.keys())
        assert not missing, f"{q.get('module')}/{q.get('qid')} missing fields: {missing}"


def test_every_question_subject_is_a_known_subject():
    """Subject should be a known Subject enum value (psm or fmt for v1)."""
    from medrack.config import Subject
    valid = {s.value for s in Subject}
    qs = get_regression_questions()
    for q in qs:
        assert q["subject"] in valid, f"{q.get('qid')}: unknown subject {q['subject']!r}"


def test_every_question_module_is_a_known_module():
    """Module should be one of the modules we have ingested.

    MedRack's on-disk layout is modules/<subject>/<module-slug>/. So
    we walk one level deep to find the known module slugs.
    """
    from pathlib import Path
    medrack_root = Path(__file__).resolve().parents[2]
    modules_dir = medrack_root / "modules"
    known_modules = set()
    for subject_dir in modules_dir.iterdir():
        if not subject_dir.is_dir():
            continue
        for module_dir in subject_dir.iterdir():
            if module_dir.is_dir():
                known_modules.add(module_dir.name)
    qs = get_regression_questions()
    for q in qs:
        assert q["module"] in known_modules, (
            f"{q['qid']}: module {q['module']!r} not in {known_modules}"
        )
