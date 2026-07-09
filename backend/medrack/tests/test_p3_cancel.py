"""P3: cooperative batch cancel and job cancel flag."""
from __future__ import annotations

from medrack.answer.batch import generate_full_batch
from medrack.answer.llm import MockLLMClient
from medrack.dashboard.jobs import JobRegistry


def test_generate_full_batch_honours_cancel_check():
    questions = [
        {
            "qid": f"q{i:03d}",
            "type": "theory",
            "question_text": f"Question {i} about antenatal care?",
            "module_chapter": "maternal",
            "marks": 5,
        }
        for i in range(1, 6)
    ]
    # Cancel before the third question is attempted (after 2 complete).
    state = {"seen": 0}

    def cancel_check():
        # Called at top of each iteration; cancel when about to start index 2.
        return state["seen"] >= 2

    class CountingMock(MockLLMClient):
        def complete(self, prompt: str, max_output_tokens: int | None = None):
            state["seen"] += 1
            return super().complete(prompt, max_output_tokens=max_output_tokens)

    # force_regenerate so we always hit the LLM (no cache).
    result = generate_full_batch(
        module_name="p3-cancel-test",
        subject="psm",
        questions=questions,
        llm_client=CountingMock(),
        force_regenerate=True,
        cancel_check=cancel_check,
        marks=5,
    )
    assert result.cancelled is True
    assert result.questions_skipped >= 1
    # At most 2 answers (cancel checked before each question; first two run,
    # third iteration sees cancel_check True before generate).
    assert len(result.answers) <= 2
    assert result.questions_total == 5


def test_job_registry_request_cancel():
    reg = JobRegistry()
    import time

    started = {"go": False}

    def body(job, progress):
        progress(10, "working")
        # Wait until cancel is requested, then exit with cancelled marker.
        for _ in range(50):
            if job.cancel_requested:
                return {"cancelled": True, "answered": 1}
            time.sleep(0.05)
        return {"cancelled": False}

    job = reg.run("test_cancel", body)
    # Give the thread a moment to start.
    for _ in range(40):
        j = reg.get(job.id)
        if j and j.status == "running":
            break
        time.sleep(0.05)
    out = reg.request_cancel(job.id)
    assert out is not None
    assert out.cancel_requested is True
    for _ in range(80):
        j = reg.get(job.id)
        if j and j.status in ("cancelled", "done", "error"):
            break
        time.sleep(0.05)
    j = reg.get(job.id)
    assert j is not None
    assert j.status == "cancelled"
    assert j.result and j.result.get("cancelled") is True
