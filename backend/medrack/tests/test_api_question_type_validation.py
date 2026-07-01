"""Regression tests: question_type must be validated at the API boundary.

The canonical allowed values are 'mcq' and 'theory' — the only dispatchers
in medrack.answer.generate.build_prompt_for_question. Anything else must
be rejected with HTTP 422 before the request reaches generate_answer().

These tests cover:
- Unit: Pydantic model validation (canonical, default, parametrised invalid)
- Integration: FastAPI route returns 422 with structured detail for invalid values
- Integration: FastAPI route accepts valid values (schema-level proof only,
  with a 1-second timeout to fail fast and skip on provider slowness)

The tests are LLM-independent: 422 is emitted by Pydantic before any handler
runs, so no OPENCODE_ZEN_API_KEY is required for the negative tests. The
positive 'accepts theory' test uses a short timeout and pytest.skips on
provider slowness — its sole purpose is to prove the schema accepts valid
values (i.e. does not return 422). It does not depend on real LLM availability.
"""
from __future__ import annotations

import pytest
import httpx
from fastapi.testclient import TestClient

from medrack.dashboard.api.v1 import GenerateRequest


VALID_QUESTION = {
    "qid": "qt-valid-001",
    "question_text": "What is the first-line treatment for status epilepticus?",
    "subject": "pharmacology",
}


def _make_request(**overrides) -> dict:
    payload = dict(VALID_QUESTION)
    payload.update(overrides)
    return payload


# --- Unit: Pydantic model --------------------------------------------------


def test_valid_theory_is_accepted():
    req = GenerateRequest(**_make_request(question_type="theory"))
    assert req.question_type == "theory"


def test_valid_mcq_is_accepted():
    req = GenerateRequest(**_make_request(question_type="mcq"))
    assert req.question_type == "mcq"


def test_default_question_type_is_theory():
    req = GenerateRequest(**_make_request())
    assert req.question_type == "theory"


def test_model_json_schema_enforces_enum():
    schema = GenerateRequest.model_json_schema()
    prop = schema["properties"]["question_type"]
    assert prop.get("enum") == ["mcq", "theory"]
    assert prop.get("default") == "theory"
    assert prop.get("type") == "string"


@pytest.mark.parametrize(
    "bad_value",
    [
        "short_answer",
        "essay",
        "long_answer",
        "MCQ",        # case-sensitive
        "Theory",     # case-sensitive
        "",
        "theory ",    # trailing whitespace
        "the0ry",     # typo
    ],
)
def test_invalid_question_type_rejected_at_model(bad_value: str):
    with pytest.raises(ValueError):
        GenerateRequest(**_make_request(question_type=bad_value))


# --- Integration: FastAPI route returns 422 --------------------------------


@pytest.fixture(scope="module")
def client():
    # Lazy import — matches the existing convention in test_dashboard_services.py
    from medrack.dashboard.api.v1 import make_app
    return TestClient(make_app())


def test_route_returns_422_for_short_answer(client):
    resp = client.post(
        "/api/v1/questions/generate",
        json=_make_request(question_type="short_answer"),
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    # Pydantic v2 surface: {"detail": [{"type": "literal_error", "loc": ["body","question_type"], ...}]}
    assert "detail" in body
    locs = [tuple(item["loc"]) for item in body["detail"]]
    assert ("body", "question_type") in locs


def test_route_returns_422_for_empty_string(client):
    resp = client.post(
        "/api/v1/questions/generate",
        json=_make_request(question_type=""),
    )
    assert resp.status_code == 422


def test_route_422_detail_includes_allowed_values(client):
    resp = client.post(
        "/api/v1/questions/generate",
        json=_make_request(question_type="essay"),
    )
    assert resp.status_code == 422
    body_text = resp.text
    # The 422 body should mention the allowed enum values so the client
    # developer can self-correct.
    assert "mcq" in body_text and "theory" in body_text, body_text


def test_route_accepts_theory_request_schema(client):
    # We only verify request validation passes (422 is NOT expected). We do
    # NOT wait for the LLM — the test client may time out or return 200/500
    # depending on provider availability, all of which prove the schema
    # accepted the payload. Use a 1-second timeout to fail fast.
    try:
        resp = client.post(
            "/api/v1/questions/generate",
            json=_make_request(question_type="theory"),
            timeout=1.0,
        )
    except httpx.TimeoutException:
        pytest.skip("LLM provider slow — schema validation passed (no 422)")
    # Schema accepted the payload — anything other than 422 is fine here.
    assert resp.status_code != 422, resp.text
