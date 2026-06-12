from typing import Any

from typing_extensions import TypedDict


class TailorState(TypedDict):
    job_id: int
    thread_id: str
    langfuse_trace_id: str
    company: str
    role: str
    jd_text: str
    jd_analysis: dict[str, Any] | None
    base_resume: dict[str, Any]
    personal: dict[str, Any]
    tailored_resume: dict[str, Any] | None
    slack_ts: str
    iteration: int
    feedback: str
    status: str
    error_count: int
    last_error: str | None
    scores: dict[str, Any] | None
