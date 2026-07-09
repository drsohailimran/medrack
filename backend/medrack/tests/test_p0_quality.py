"""P0 quality gates — unit tests (no live LLM required)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from medrack.answer.prompt import build_theory_prompt, build_mcq_prompt
from medrack.validation.pipeline import ValidationPipeline
from medrack.validation.rules import GroundingRule, ScopeLengthRule, TruncationRule
from medrack.validation.result import Severity


# ---------------------------------------------------------------------------
# Prompt: scope + grounding language present
# ---------------------------------------------------------------------------

def test_theory_prompt_has_scope_and_grounding_blocks():
    result = build_theory_prompt(
        question_text="Enumerate the objectives of antenatal care.",
        retrieved_chunks=["ANC includes early registration, screening, IFA, TT."],
        marks=3,
        subject="psm",
    )
    p = result.prompt
    assert "SCOPE CONTROL" in p
    assert "HARD GROUNDING" in p
    assert "LENGTH BAND" in p
    assert "HARD MINIMUM" in p
    assert "PRAMS" in p  # denylist instruction present
    assert "3-mark" in p or "3-mark questions" in p or "3-mark:" in p


def test_mcq_prompt_has_grounding_rules():
    result = build_mcq_prompt(
        question_text="WHO definition of health excludes:",
        options={"a": "Social", "b": "Physical", "c": "Mental", "d": "Economic"},
        retrieved_chunks=["WHO: physical, mental, social well-being."],
        subject="psm",
    )
    assert "HARD GROUNDING" in result.prompt
    assert "SCOPE" in result.prompt


# ---------------------------------------------------------------------------
# GroundingRule
# ---------------------------------------------------------------------------

def test_grounding_fails_on_prams():
    rule = GroundingRule()
    answer = (
        "Objectives of ANC\n"
        "• Screening via Pregnancy Risk Assessment Monitoring System (PRAMS).\n"
        "• Give IFA tablets.\n"
    )
    source = "ANC includes early registration, weight, BP, IFA, TT immunization."
    result = rule.check(answer, context={"source_text": source, "marks": 3})
    assert result.severity == Severity.FAIL
    assert any(i["token"] == "PRAMS" for i in (result.details or {}).get("issues", []))


def test_grounding_passes_when_scheme_in_source():
    rule = GroundingRule()
    answer = "• JSY provides cash assistance for institutional delivery.\n"
    source = "Janani Suraksha Yojana (JSY) is a safe motherhood intervention under NHM."
    result = rule.check(answer, context={"source_text": source})
    assert result.severity == Severity.PASS


def test_grounding_fails_invented_yojana_not_in_source():
    rule = GroundingRule()
    answer = "• Ashwini Health Yojana covers free transport.\n"
    source = "JSY and JSSK support maternal health under NHM."
    result = rule.check(answer, context={"source_text": source})
    assert result.severity == Severity.FAIL


# ---------------------------------------------------------------------------
# ScopeLengthRule
# ---------------------------------------------------------------------------

def test_scope_length_fails_3mark_laundry_list():
    rule = ScopeLengthRule()
    # ~300+ words of filler
    filler = " ".join(["word"] * 300)
    result = rule.check(filler, context={"marks": 3})
    assert result.severity == Severity.FAIL


def test_scope_length_fails_10mark_half_length():
    rule = ScopeLengthRule()
    short = " ".join(["word"] * 400)  # under min 550 for 10-mark
    result = rule.check(short, context={"marks": 10, "target_word_count": 750})
    assert result.severity == Severity.FAIL
    assert "under-length" in (result.message or "").lower()


def test_scope_length_passes_short_3mark():
    rule = ScopeLengthRule()
    # Comfortably inside 3-mark band for target 125 (min ~94, max 200)
    answer = " ".join(["word"] * 120)
    result = rule.check(answer, context={"marks": 3, "target_word_count": 125})
    assert result.severity == Severity.PASS, result.message


def test_grounding_allows_eoc_acronym():
    rule = GroundingRule()
    answer = "• Essential Obstetric Care (EOC) includes skilled attendance and referral.\n"
    source = "Essential obstetric care at PHC with skilled birth attendants under RCH."
    result = rule.check(answer, context={"source_text": source})
    assert result.severity == Severity.PASS


def test_grounding_allows_mhm_acronym():
    rule = GroundingRule()
    answer = "• Menstrual hygiene management (MHM) education reduces infection risk.\n"
    source = "Adolescent girls need education on hygiene during menstruation."
    result = rule.check(answer, context={"source_text": source})
    assert result.severity == Severity.PASS


def test_scope_length_fails_5mark_overshoot():
    rule = ScopeLengthRule()
    long = " ".join(["word"] * 500)
    result = rule.check(long, context={"marks": 5, "target_word_count": 375})
    assert result.severity == Severity.FAIL
    assert "over-long" in (result.message or "").lower()


def test_scope_length_passes_5mark_compact_262():
    """P0.3: compact correct 5-mark (~262w) should pass (min ~255)."""
    rule = ScopeLengthRule()
    body = " ".join(["word"] * 262)
    result = rule.check(body, context={"marks": 5, "target_word_count": 375})
    assert result.severity == Severity.PASS, result.message


def test_grounding_allows_pmmvy_title():
    rule = GroundingRule()
    answer = (
        "• Under Pradhan Mantri Matru Vandana Yojana eligible mothers get cash incentive.\n"
    )
    source = "High-risk pregnancies are referred under NHM for specialized care."
    result = rule.check(answer, context={"source_text": source})
    assert result.severity == Severity.PASS, result.message


def test_scope_length_fails_10mark_1142_overshoot():
    """P0.4: 1142-word 10-mark (as seen on open EOC stem) must fail."""
    rule = ScopeLengthRule()
    long = " ".join(["word"] * 1142)
    result = rule.check(long, context={"marks": 10, "target_word_count": 750})
    assert result.severity == Severity.FAIL
    assert "over-long" in (result.message or "").lower()


def test_theory_prompt_10mark_has_anti_laundry_rules():
    result = build_theory_prompt(
        question_text="What is Essential Obstetric Care under RCH II?",
        retrieved_chunks=["EOC is basic maternity care at PHC/CHC under RCH-II."],
        marks=10,
        subject="psm",
    )
    p = result.prompt
    assert "laundry list" in p.lower() or "STOP" in p
    assert "HARD MAXIMUM" in p
    assert str(int(750 * 1.1)) in p or "825" in p or "upper" in p.lower()


# ---------------------------------------------------------------------------
# TruncationRule
# ---------------------------------------------------------------------------

def test_truncation_fails_on_connector_ending():
    rule = TruncationRule()
    result = rule.check("The main components include")
    assert result.severity == Severity.FAIL


def test_truncation_passes_clean_ending():
    rule = TruncationRule()
    result = rule.check("• Early registration is essential for risk detection.")
    assert result.severity == Severity.PASS


# ---------------------------------------------------------------------------
# Full pipeline with context
# ---------------------------------------------------------------------------

def test_pipeline_fails_prams_answer():
    pipe = ValidationPipeline()
    answer = (
        "Definition\n"
        "• ANC is care during pregnancy.\n"
        "Programmes\n"
        "• PRAMS is used for risk assessment in India.\n"
    )
    report = pipe.validate(
        answer,
        context={
            "source_text": "ANC: early registration, IFA, TT. JSY for institutional delivery.",
            "marks": 5,
            "subject": "psm",
        },
    )
    assert report.pass_ is False
    assert "GroundingRule" in report.failed_rules


def test_pipeline_passes_clean_short_answer():
    pipe = ValidationPipeline()
    # On-scope 3-mark answer with enough words for the min band.
    body = (
        "Objectives\n"
        "• Early registration of pregnancy for risk assessment.\n"
        "• Risk screening for blood pressure and anaemia.\n"
        "• IFA supplementation and TT immunization as scheduled.\n"
        "• Birth preparedness and danger-sign counselling.\n"
    ) + " " + " ".join(["detail"] * 100)
    report = pipe.validate(
        body,
        context={
            "source_text": (
                "Objectives of antenatal care include early registration, "
                "screening for risk factors, IFA, TT immunization, and counselling."
            ),
            "marks": 3,
            "subject": "psm",
            "target_word_count": 125,
        },
    )
    assert report.pass_ is True, (report.failed_rules, len(body.split()))


# ---------------------------------------------------------------------------
# Stale regenerate + kb_revision
# ---------------------------------------------------------------------------

def test_kb_revision_bump_marks_answers_stale(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "answers").mkdir(parents=True, exist_ok=True)

    from medrack.answer.kb_revision import bump_kb_revision, get_kb_revision
    from medrack.answer.versioning import is_stale

    assert get_kb_revision("psm") == 0
    from medrack import config as _cfg
    answer = {
        "module_subject": "psm",
        "versions": dict(_cfg.PIPELINE_VERSIONS),
        "embedding_model": _cfg.EMBEDDING_MODEL,
        "kb_revision": 0,
    }
    stale, reasons = is_stale(answer)
    assert stale is False

    bump_kb_revision("psm")
    stale2, reasons2 = is_stale(answer)
    assert stale2 is True
    assert "kb_reindexed" in reasons2


def test_generate_regenerates_when_stale(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, patch

    monkeypatch.setenv("MEDRACK_HOME", str(tmp_path))
    (tmp_path / "index" / "chroma").mkdir(parents=True, exist_ok=True)
    (tmp_path / "answers").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)

    from medrack.answer.cache import save_answer
    from medrack.answer.generate import generate_answer
    from medrack.answer.llm import LLMResponse

    q = {
        "qid": "q_p0",
        "type": "theory",
        "question_text": "Enumerate objectives of ANC.",
        "marks": 3,
        "module_chapter": "ch1",
    }
    # Pre-seed a "stale" cache entry (missing versions → stale)
    save_answer("mod", "ch1", "q_p0", {
        "qid": "q_p0",
        "answer_text": "OLD STALE ANSWER",
        "module_subject": "psm",
        # no versions field → is_stale True
    })

    client = MagicMock()
    client.complete.return_value = LLMResponse(
        text="Objectives\n• Early registration\n• Screening\n• IFA and TT\n",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        model="test",
        latency_seconds=0.1,
    )
    client.model = "test"

    from types import SimpleNamespace
    with patch("medrack.answer.generate._embed_query", return_value=[0.0] * 384), \
         patch("medrack.retrieval.retrieve_for_question") as mock_ret:
        mock_ret.return_value = SimpleNamespace(
            chunks=[],
            top_k=8,
            metadata_filter_active=False,
            analysis=SimpleNamespace(target_sections=[]),
        )
        out = generate_answer(
            module_name="mod",
            subject="psm",
            chapter="ch1",
            question=q,
            llm_client=client,
            marks=3,
        )
    assert client.complete.called
    assert out["cache_hit"] is False
    assert "OLD STALE" not in out["answer_text"]
    assert "validation" in out
    assert "needs_review" in out


# ---------------------------------------------------------------------------
# Regression dataset file present
# ---------------------------------------------------------------------------

def _p0_dataset_path() -> Path:
    candidates = [
        Path(__file__).resolve().parent / "regression_datasets" / "p0_quality.json",
        Path("/home/sohail/medrack/backend/medrack/tests/regression_datasets/p0_quality.json"),
    ]
    found = next((p for p in candidates if p.is_file()), None)
    assert found is not None, "p0_quality.json regression pack missing"
    return found


def test_p0_regression_dataset_file_exists():
    data = json.loads(_p0_dataset_path().read_text(encoding="utf-8"))
    assert data.get("_version") == 1
    assert len(data.get("cases", [])) >= 4


def test_p0_regression_dataset_cases_match_validator():
    """Run every fixture case through ValidationPipeline."""
    data = json.loads(_p0_dataset_path().read_text(encoding="utf-8"))
    pipe = ValidationPipeline()
    for case in data["cases"]:
        answer = case["answer_text"]
        if answer == "WORD_PAD":
            answer = " ".join(["word"] * 300)
        report = pipe.validate(
            answer,
            context={
                "source_text": case.get("source_text", ""),
                "marks": case.get("marks"),
                "subject": case.get("subject", "psm"),
            },
        )
        if case["expect_pass"]:
            assert report.pass_ is True, f"{case['id']} should pass; failed={report.failed_rules}"
        else:
            assert report.pass_ is False, f"{case['id']} should fail"
            expected_any = case.get("expect_failed_rules_any") or []
            if expected_any:
                assert any(r in report.failed_rules for r in expected_any), (
                    f"{case['id']}: expected one of {expected_any}, got {report.failed_rules}"
                )
