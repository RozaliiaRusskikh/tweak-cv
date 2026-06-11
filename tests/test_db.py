from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from tweakcv.db import Base, Job, JobStatus, ResumeVersion


@pytest.fixture()
def mem_session() -> Generator[Session]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(engine)


def test_init_db_creates_tables(mem_session: Session) -> None:
    inspector = inspect(mem_session.get_bind())
    tables = inspector.get_table_names()
    assert "jobs" in tables
    assert "resume_versions" in tables


def test_job_status_enum_values() -> None:
    assert JobStatus.pending.value == "pending"
    assert JobStatus.approved.value == "approved"
    assert JobStatus.rejected.value == "rejected"
    assert JobStatus.expired.value == "expired"
    assert JobStatus.failed.value == "failed"


def test_resume_version_cascade_delete(mem_session: Session) -> None:
    job = Job(
        company="Acme",
        role="Eng",
        jd_text="...",
        status=JobStatus.pending.value,
        thread_id="t1",
    )
    mem_session.add(job)
    mem_session.flush()

    rv = ResumeVersion(job_id=job.id, version=1, content="{}", approved=False)
    mem_session.add(rv)
    mem_session.commit()

    assert mem_session.query(ResumeVersion).count() == 1

    mem_session.delete(job)
    mem_session.commit()

    assert mem_session.query(ResumeVersion).count() == 0


def test_job_default_status(mem_session: Session) -> None:
    job = Job(
        company="X",
        role="Y",
        jd_text="z",
        status=JobStatus.pending.value,
        thread_id="t2",
    )
    mem_session.add(job)
    mem_session.commit()
    mem_session.refresh(job)
    assert job.status == JobStatus.pending.value


def test_thread_id_unique_constraint(mem_session: Session) -> None:
    job1 = Job(company="A", role="B", jd_text="c", status=JobStatus.pending.value, thread_id="same")
    job2 = Job(company="D", role="E", jd_text="f", status=JobStatus.pending.value, thread_id="same")
    mem_session.add(job1)
    mem_session.commit()
    mem_session.add(job2)
    with pytest.raises(Exception, match="UNIQUE constraint"):
        mem_session.commit()
