from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from tweakcv.db import Base, Job, JobStatus
from tweakcv.runner import stale_sweep


def _make_engine() -> Engine:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine


def test_stale_sweep_expires_old_pending_job() -> None:
    engine = _make_engine()
    TestSession = sessionmaker(bind=engine)

    old_ts = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25)
    with Session(engine) as setup_session:
        old_job = Job(
            company="Old Co",
            role="Eng",
            jd_text="...",
            status=JobStatus.pending.value,
            thread_id="stale-thread-1",
            slack_ts="ts_old",
            last_activity_at=old_ts,
        )
        setup_session.add(old_job)
        setup_session.commit()
        job_id = old_job.id

    mock_slack = MagicMock()
    mock_graph = MagicMock()

    from unittest.mock import patch

    with patch("tweakcv.runner.SessionLocal", TestSession):
        stale_sweep(mock_slack, mock_graph)

    with Session(engine) as verify_session:
        job = verify_session.get(Job, job_id)
        assert job is not None
        assert job.status == JobStatus.expired.value

    mock_slack.chat_update.assert_called_once()
    mock_graph.invoke.assert_called_once()
    engine.dispose()


def test_stale_sweep_does_not_expire_recent_job() -> None:
    engine = _make_engine()
    TestSession = sessionmaker(bind=engine)

    with Session(engine) as setup_session:
        recent_job = Job(
            company="New Co",
            role="Dev",
            jd_text="...",
            status=JobStatus.pending.value,
            thread_id="fresh-thread-1",
            slack_ts="ts_new",
        )
        setup_session.add(recent_job)
        setup_session.commit()
        job_id = recent_job.id

    mock_slack = MagicMock()
    mock_graph = MagicMock()

    from unittest.mock import patch

    with patch("tweakcv.runner.SessionLocal", TestSession):
        stale_sweep(mock_slack, mock_graph)

    with Session(engine) as verify_session:
        job = verify_session.get(Job, job_id)
        assert job is not None
        assert job.status == JobStatus.pending.value

    mock_slack.chat_update.assert_not_called()
    mock_graph.invoke.assert_not_called()
    engine.dispose()
