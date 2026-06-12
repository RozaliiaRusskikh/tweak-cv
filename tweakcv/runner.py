"""Core job creation and graph invocation — shared by slack_handler and main.py."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphInterrupt
from langgraph.types import Command
from loguru import logger

from tweakcv.clients import get_langfuse
from tweakcv.db import Job, JobStatus, SessionLocal
from tweakcv.settings import settings
from tweakcv.state import TailorState

_BASE_RESUME_PATH = Path(__file__).parent / "base_resume.json"
_PERSONAL_PATH = Path(__file__).parent / "personal.json"


def stale_sweep(slack: Any, graph: Any) -> None:
    """Expire pending jobs older than 24h and resume graph with 'expired' command.

    Called once at startup. Accepts slack client and graph as parameters so the
    function is independently testable without relying on module-level singletons.
    """
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
    with SessionLocal() as db:
        stale = (
            db.query(Job)
            .filter(Job.status == JobStatus.pending.value, Job.last_activity_at < cutoff)
            .all()
        )
        for job in stale:
            try:
                if job.slack_ts:
                    slack.chat_update(
                        channel=settings.slack_channel_id,
                        ts=job.slack_ts,
                        text="⏰ Expired – no action taken (24h passed)",
                        blocks=[],
                    )
                config: dict[str, Any] = {"configurable": {"thread_id": job.thread_id}}
                graph.invoke(Command(resume="expired"), config=config)
                job.status = JobStatus.expired.value
            except Exception as exc:
                logger.error(f"stale_sweep_failed job_id={job.id} error={exc}")
        if stale:
            db.commit()
            logger.info(f"stale_sweep_done count={len(stale)}")


def run_job(jd_text: str, graph: Any, loading_ts: str = "") -> int:
    """Create a Job row, build initial state, invoke the graph.

    Returns job_id. Raises on hard failure.
    Handles GraphInterrupt silently (expected: graph paused at await_feedback).
    """
    base_resume: dict[str, Any] = json.loads(_BASE_RESUME_PATH.read_text())
    personal: dict[str, Any] = (
        json.loads(_PERSONAL_PATH.read_text()) if _PERSONAL_PATH.exists() else {}
    )

    langfuse = get_langfuse()
    trace_id = langfuse.create_trace_id()
    langfuse.start_observation(
        trace_context={"trace_id": trace_id},
        name="resume-tailoring",
        input={"jd_text": jd_text[:500]},
    ).end()

    thread_id = str(uuid4())
    with SessionLocal() as db:
        job = Job(
            company="",
            role="",
            jd_text=jd_text,
            status=JobStatus.pending.value,
            thread_id=thread_id,
            langfuse_trace_id=trace_id,
        )
        db.add(job)
        db.flush()
        job_id = job.id
        db.commit()

    initial_state: TailorState = {
        "job_id": job_id,
        "thread_id": thread_id,
        "langfuse_trace_id": trace_id,
        "company": "",
        "role": "",
        "jd_text": jd_text,
        "jd_analysis": None,
        "base_resume": base_resume,
        "personal": personal,
        "tailored_resume": None,
        "slack_ts": loading_ts,
        "iteration": 0,
        "feedback": "",
        "status": "pending",
        "error_count": 0,
        "last_error": None,
        "scores": None,
    }

    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    logger.info(f"run_job_start job_id={job_id} thread_id={thread_id}")
    try:
        graph.invoke(initial_state, config=config)
    except GraphInterrupt:
        logger.info(f"run_job_paused job_id={job_id}")
    except Exception as exc:
        logger.error(f"run_job_failed job_id={job_id} error={exc}")
        raise

    return job_id
