from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tweakcv.db import Base, Job, JobStatus, ResumeVersion
from tweakcv.nodes.finalize import finalize_node
from tweakcv.state import TailorState

TAILORED = {
    "summary": "Great engineer",
    "experience": [{"company": "Acme", "role": "Eng", "dates": "2022", "bullets": []}],
    "skills": ["Python"],
    "education": [{"institution": "MIT", "degree": "B.S.", "year": "2018"}],
}
BASE = {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "+1-555-0000",
    "location": "SF",
    "linkedin": "",
    "github": "",
    "summary": "Engineer",
    "experience": [{"company": "Acme", "role": "Eng", "dates": "2022", "bullets": []}],
    "skills": ["Python"],
    "education": [{"institution": "MIT", "degree": "B.S.", "year": "2018"}],
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
        role="Platform Engineer",
        jd_text="...",
        status=JobStatus.pending.value,
        thread_id="t-fin-1",
    )
    session.add(job)
    session.flush()
    job_id = job.id
    session.commit()
    return job_id


def _state(job_id: int) -> TailorState:
    return {
        "job_id": job_id,
        "thread_id": "t-fin-1",
        "langfuse_trace_id": "lf-fin-1",
        "company": "Acme",
        "role": "Platform Engineer",
        "jd_text": "...",
        "jd_analysis": {"keywords": ["Python"]},
        "base_resume": BASE,
        "personal": {},
        "tailored_resume": TAILORED,
        "slack_ts": "123.456",
        "iteration": 0,
        "feedback": "approve",
        "status": "pending",
        "error_count": 0,
        "last_error": None,
        "scores": {"keyword_coverage": 0.8, "no_hallucination": True},
    }


def test_finalize_node_creates_pdf_and_updates_db(mem_session: Session, tmp_path: Path) -> None:
    job_id = _make_job(mem_session)
    state = _state(job_id)

    mock_weasy = MagicMock()
    mock_langfuse_client = MagicMock()
    mock_slack = MagicMock()

    mock_weasyprint_module = MagicMock()
    mock_weasyprint_module.HTML.return_value = mock_weasy

    with (
        patch.dict("sys.modules", {"weasyprint": mock_weasyprint_module}),
        patch("tweakcv.nodes.finalize._OUTPUT_DIR", tmp_path),
        patch("tweakcv.nodes.finalize.SessionLocal", return_value=mem_session),
        patch("tweakcv.nodes.finalize.get_langfuse", return_value=mock_langfuse_client),
        patch("tweakcv.nodes.finalize.get_slack", return_value=mock_slack),
    ):
        result = finalize_node(state)

    assert result["status"] == "approved"
    mock_weasy.write_pdf.assert_called_once()

    mem_session.expire_all()
    job = mem_session.get(Job, job_id)
    assert job is not None
    assert job.status == JobStatus.approved.value

    rv = mem_session.query(ResumeVersion).filter_by(job_id=job_id, approved=True).first()
    assert rv is not None


def test_finalize_node_logs_user_approval_to_langfuse(mem_session: Session, tmp_path: Path) -> None:
    job_id = _make_job(mem_session)
    state = _state(job_id)

    mock_weasy = MagicMock()
    mock_langfuse_client = MagicMock()
    mock_slack = MagicMock()

    mock_weasyprint_module = MagicMock()
    mock_weasyprint_module.HTML.return_value = mock_weasy

    with (
        patch.dict("sys.modules", {"weasyprint": mock_weasyprint_module}),
        patch("tweakcv.nodes.finalize._OUTPUT_DIR", tmp_path),
        patch("tweakcv.nodes.finalize.SessionLocal", return_value=mem_session),
        patch("tweakcv.nodes.finalize.get_langfuse", return_value=mock_langfuse_client),
        patch("tweakcv.nodes.finalize.get_slack", return_value=mock_slack),
    ):
        finalize_node(state)

    mock_langfuse_client.create_score.assert_called_once_with(
        trace_id="lf-fin-1", name="user_approval", value=1.0, comment="approve"
    )
