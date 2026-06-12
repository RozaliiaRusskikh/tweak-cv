import enum
from collections.abc import Generator
from datetime import datetime

from loguru import logger
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from tweakcv.settings import settings


class Base(DeclarativeBase):
    pass


class JobStatus(enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    failed = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    jd_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Stored as a plain string; use JobStatus.X.value when writing, compare with .value when reading
    status: Mapped[str] = mapped_column(Text, nullable=False, default=JobStatus.pending.value)
    thread_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    slack_ts: Mapped[str | None] = mapped_column(Text, nullable=True)
    langfuse_trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    resume_versions: Mapped[list["ResumeVersion"]] = relationship(
        "ResumeVersion", back_populates="job", cascade="all, delete-orphan"
    )


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keyword_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    job: Mapped["Job"] = relationship("Job", back_populates="resume_versions")


_idx_rv_job = Index("idx_resume_versions_job_id", ResumeVersion.job_id)
_idx_jobs_status = Index("idx_jobs_status_activity", Job.status, Job.last_activity_at)

_engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

SessionLocal: sessionmaker[Session] = sessionmaker(bind=_engine)


def init_db() -> None:
    Base.metadata.create_all(_engine)
    logger.info(f"db_initialised url={settings.database_url}")


def get_db() -> Generator[Session]:
    with Session(_engine) as session:
        yield session
