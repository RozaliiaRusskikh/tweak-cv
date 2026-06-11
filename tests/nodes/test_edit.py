import json
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tweakcv.db import Base, Job, JobStatus, ResumeVersion
from tweakcv.nodes.edit import edit_node
from tweakcv.schemas import ExperienceEntry, TailoredResumeOutput
from tweakcv.state import TailorState

TAILORED = {
    "summary": "Python engineer",
    "experience": [{"company": "Acme", "role": "Eng", "dates": "2022", "bullets": ["Built APIs"]}],
    "skills": ["Python"],
    "education": [],
}
BASE = {
    "name": "Jane",
    "summary": "Eng",
    "experience": [{"company": "Acme", "role": "Eng", "dates": "2022", "bullets": ["Built APIs"]}],
    "skills": ["Python"],
    "education": [],
}


@pytest.fixture()
def mem_session() -> Generator[Session]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(engine)


def _make_job(session: Session) -> int:
    job = Job(
        company="Acme",
        role="Eng",
        jd_text="...",
        status=JobStatus.pending.value,
        thread_id="t-edit-1",
    )
    session.add(job)
    session.flush()
    jid = job.id
    session.commit()
    return jid


def _state(
    job_id: int, feedback: str = "edit:emphasise leadership", iteration: int = 1
) -> TailorState:
    return {
        "job_id": job_id,
        "thread_id": "t-edit-1",
        "langfuse_trace_id": "lf-edit-1",
        "company": "Acme",
        "role": "Eng",
        "jd_text": "Python APIs leadership",
        "jd_analysis": {"keywords": ["Python", "leadership"]},
        "base_resume": BASE,
        "personal": {},
        "tailored_resume": TAILORED,
        "slack_ts": "ts1",
        "iteration": iteration,
        "feedback": feedback,
        "status": "pending",
        "error_count": 0,
        "last_error": None,
        "scores": {"keyword_coverage": 0.5, "no_hallucination": True},
    }


def test_edit_node_increments_iteration(mem_session: Session) -> None:
    job_id = _make_job(mem_session)
    state = _state(job_id, iteration=1)

    edited_resume = TailoredResumeOutput(
        summary="Leadership-focused Python engineer",
        experience=[
            ExperienceEntry(company="Acme", role="Eng", dates="2022", bullets=["Led team"])
        ],
        skills=["Python"],
        education=[],
    )
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.return_value = edited_resume
    mock_score = MagicMock()
    mock_score.keyword_coverage = 0.8
    mock_score.no_hallucination = True
    mock_score.edit_fidelity = 0.9
    mock_score.needs_retry = False
    mock_score.model_dump.return_value = {"keyword_coverage": 0.8}

    with (
        patch("tweakcv.nodes.edit.get_llm", return_value=mock_llm),
        patch("tweakcv.nodes.edit.get_prompt", return_value="prompt"),
        patch("tweakcv.nodes.edit.score", return_value=mock_score),
        patch("tweakcv.nodes.edit.SessionLocal", return_value=mem_session),
    ):
        result = edit_node(state)

    assert result["iteration"] == 2
    assert result["feedback"] == ""


def test_edit_node_saves_resume_version(mem_session: Session) -> None:
    job_id = _make_job(mem_session)
    state = _state(job_id, iteration=1)

    edited_resume = TailoredResumeOutput(
        summary="Updated",
        experience=[],
        skills=["Python"],
        education=[],
    )
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.return_value = edited_resume
    mock_score = MagicMock()
    mock_score.keyword_coverage = 0.7
    mock_score.model_dump.return_value = {}

    with (
        patch("tweakcv.nodes.edit.get_llm", return_value=mock_llm),
        patch("tweakcv.nodes.edit.get_prompt", return_value="prompt"),
        patch("tweakcv.nodes.edit.score", return_value=mock_score),
        patch("tweakcv.nodes.edit.SessionLocal", return_value=mem_session),
    ):
        edit_node(state)

    mem_session.expire_all()
    rv = mem_session.query(ResumeVersion).filter_by(job_id=job_id).first()
    assert rv is not None
    assert rv.version == 2
    assert rv.approved is False
    content = json.loads(rv.content)
    assert content["summary"] == "Updated"


def test_edit_node_strips_edit_prefix_from_feedback(mem_session: Session) -> None:
    job_id = _make_job(mem_session)
    state = _state(job_id, feedback="edit:fix the tone")

    captured_human: list[str] = []

    edited_resume = TailoredResumeOutput(summary="Fixed", experience=[], skills=[], education=[])

    def _invoke(msgs: list[Any]) -> TailoredResumeOutput:
        captured_human.append(msgs[1].content)
        return edited_resume

    mock_chain = MagicMock()
    mock_chain.invoke.side_effect = _invoke
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain
    mock_score = MagicMock()
    mock_score.keyword_coverage = 0.5
    mock_score.model_dump.return_value = {}

    with (
        patch("tweakcv.nodes.edit.get_llm", return_value=mock_llm),
        patch("tweakcv.nodes.edit.get_prompt", return_value="prompt"),
        patch("tweakcv.nodes.edit.score", return_value=mock_score),
        patch("tweakcv.nodes.edit.SessionLocal", return_value=mem_session),
    ):
        edit_node(state)

    assert captured_human, "LLM was never invoked"
    import json as _json

    payload = _json.loads(captured_human[0])
    assert payload["edit_request"] == "fix the tone"
