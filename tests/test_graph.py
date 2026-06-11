from typing import Any

from tweakcv.graph import route_feedback
from tweakcv.state import TailorState


def _state(**kwargs: Any) -> TailorState:
    """Build a minimal TailorState with sensible defaults."""
    defaults: dict[str, Any] = {
        "job_id": 1,
        "thread_id": "t1",
        "langfuse_trace_id": "lf1",
        "company": "Acme",
        "role": "Eng",
        "jd_text": "...",
        "jd_analysis": None,
        "base_resume": {},
        "tailored_resume": None,
        "slack_ts": "",
        "iteration": 0,
        "feedback": "",
        "status": "pending",
        "error_count": 0,
        "last_error": None,
        "scores": None,
    }
    defaults.update(kwargs)
    return defaults  # type: ignore[return-value]


def test_route_feedback_approve() -> None:
    assert route_feedback(_state(feedback="approve")) == "approve"


def test_route_feedback_reject() -> None:
    assert route_feedback(_state(feedback="reject")) == "reject"


def test_route_feedback_expired_via_feedback() -> None:
    assert route_feedback(_state(feedback="expired")) == "expired"


def test_route_feedback_expired_via_status() -> None:
    assert route_feedback(_state(status="expired")) == "expired"


def test_route_feedback_edit_with_text() -> None:
    assert route_feedback(_state(feedback="edit:fix the summary", iteration=1)) == "edit"


def test_route_feedback_edit_bare() -> None:
    assert route_feedback(_state(feedback="edit", iteration=0)) == "edit"


def test_route_feedback_hard_stop_at_iteration_4() -> None:
    result = route_feedback(_state(feedback="edit:something", iteration=4))
    assert result == "reject"


def test_route_feedback_hard_stop_above_iteration_4() -> None:
    result = route_feedback(_state(feedback="edit:something", iteration=5))
    assert result == "reject"


def test_route_feedback_failed_status_routes_to_error() -> None:
    assert route_feedback(_state(status="failed")) == "error"


def test_route_feedback_iteration_3_still_allows_edit() -> None:
    assert route_feedback(_state(feedback="edit:tweak", iteration=3)) == "edit"
