from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tweakcv.db import Base, Job, JobStatus
from tweakcv.nodes.analyze import analyze_node
from tweakcv.schemas import JDAnalysisOutput
from tweakcv.state import TailorState


@pytest.fixture()
def mem_session() -> Generator[Session]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(engine)


def _make_job(session: Session) -> int:
    job = Job(
        company="",
        role="",
        jd_text="...",
        status=JobStatus.pending.value,
        thread_id="t1",
    )
    session.add(job)
    session.flush()
    job_id = job.id
    session.commit()
    return job_id


def _state(job_id: int) -> TailorState:
    return {
        "job_id": job_id,
        "thread_id": "t1",
        "langfuse_trace_id": "lf1",
        "company": "",
        "role": "",
        "jd_text": "We are looking for a Senior Python Engineer at Acme Corp.",
        "jd_analysis": None,
        "base_resume": {},
        "personal": {},
        "tailored_resume": None,
        "slack_ts": "",
        "iteration": 0,
        "feedback": "",
        "status": "pending",
        "error_count": 0,
        "last_error": None,
        "scores": None,
    }


def test_analyze_node_returns_jd_analysis_company_role(mem_session: Session) -> None:
    job_id = _make_job(mem_session)
    mock_result = JDAnalysisOutput(
        company="Acme Corp",
        role="Senior Python Engineer",
        required_skills=["Python"],
        preferred_skills=[],
        keywords=["Python", "FastAPI"],
    )

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value.invoke.return_value = mock_result

    with (
        patch("tweakcv.nodes.analyze.get_llm", return_value=mock_llm),
        patch("tweakcv.nodes.analyze.get_prompt", return_value="system prompt"),
        patch("tweakcv.nodes.analyze.SessionLocal", return_value=mem_session),
    ):
        result = analyze_node(_state(job_id))

    assert result["company"] == "Acme Corp"
    assert result["role"] == "Senior Python Engineer"
    assert result["jd_analysis"]["keywords"] == ["Python", "FastAPI"]


def test_analyze_node_passes_jd_text_to_llm(mem_session: Session) -> None:
    job_id = _make_job(mem_session)
    mock_result = JDAnalysisOutput(
        company="X",
        role="Y",
        required_skills=[],
        preferred_skills=[],
        keywords=[],
    )
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = mock_result
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain

    state = _state(job_id)

    with (
        patch("tweakcv.nodes.analyze.get_llm", return_value=mock_llm),
        patch("tweakcv.nodes.analyze.get_prompt", return_value="prompt"),
        patch("tweakcv.nodes.analyze.SessionLocal", return_value=mem_session),
    ):
        analyze_node(state)

    call_args = mock_chain.invoke.call_args[0][0]
    # Second message (HumanMessage) should contain the JD text
    assert state["jd_text"] in call_args[1].content
