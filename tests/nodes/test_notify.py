from typing import Any

from tweakcv.nodes.notify import _build_blocks
from tweakcv.state import TailorState

TAILORED = {
    "summary": "Python engineer",
    "experience": [],
    "skills": ["Python"],
    "education": [],
}


def _state(**kwargs: Any) -> TailorState:
    defaults: dict[str, Any] = {
        "job_id": 1,
        "thread_id": "t1",
        "langfuse_trace_id": "lf1",
        "company": "Acme",
        "role": "Platform Engineer",
        "jd_text": "...",
        "jd_analysis": None,
        "base_resume": {},
        "tailored_resume": TAILORED,
        "slack_ts": "",
        "iteration": 0,
        "feedback": "",
        "status": "pending",
        "error_count": 0,
        "last_error": None,
        "scores": {"keyword_coverage": 0.8, "no_hallucination": True},
    }
    defaults.update(kwargs)
    return defaults  # type: ignore[return-value]


def _get_action_ids(blocks: list[dict[str, Any]]) -> list[str]:
    for block in blocks:
        if block.get("type") == "actions":
            return [el["action_id"] for el in block.get("elements", [])]
    return []


def test_blocks_include_all_three_buttons_by_default() -> None:
    blocks = _build_blocks(_state(iteration=0))
    action_ids = _get_action_ids(blocks)
    assert "approve_resume" in action_ids
    assert "edit_resume" in action_ids
    assert "reject_resume" in action_ids


def test_blocks_omit_edit_button_at_iteration_4() -> None:
    blocks = _build_blocks(_state(iteration=4))
    action_ids = _get_action_ids(blocks)
    assert "edit_resume" not in action_ids
    assert "approve_resume" in action_ids
    assert "reject_resume" in action_ids


def test_blocks_omit_edit_button_above_iteration_4() -> None:
    blocks = _build_blocks(_state(iteration=5))
    action_ids = _get_action_ids(blocks)
    assert "edit_resume" not in action_ids


def test_blocks_include_edit_button_at_iteration_3() -> None:
    blocks = _build_blocks(_state(iteration=3))
    action_ids = _get_action_ids(blocks)
    assert "edit_resume" in action_ids


def test_last_edit_warning_shown_at_iteration_3() -> None:
    blocks = _build_blocks(_state(iteration=3))
    context_texts = [
        el["text"]
        for block in blocks
        if block.get("type") == "context"
        for el in block.get("elements", [])
    ]
    assert any("last edit" in t.lower() for t in context_texts)


def test_no_warning_at_iteration_2() -> None:
    blocks = _build_blocks(_state(iteration=2))
    context_blocks = [b for b in blocks if b.get("type") == "context"]
    # Context block may be absent or present without the warning
    for block in context_blocks:
        for el in block.get("elements", []):
            assert "last edit" not in el.get("text", "").lower()


def test_header_contains_company_and_role() -> None:
    blocks = _build_blocks(_state())
    header = next(b for b in blocks if b.get("type") == "header")
    assert "Acme" in header["text"]["text"]
    assert "Platform Engineer" in header["text"]["text"]


def test_button_values_contain_job_id() -> None:
    blocks = _build_blocks(_state(job_id=42))
    for block in blocks:
        if block.get("type") == "actions":
            for el in block["elements"]:
                assert el["value"] == "42"
