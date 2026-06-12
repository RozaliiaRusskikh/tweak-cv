from typing import Any

from loguru import logger

from tweakcv.clients import get_langfuse, get_slack
from tweakcv.db import Job, JobStatus, SessionLocal
from tweakcv.settings import settings
from tweakcv.state import TailorState


def _user_friendly_error(error_msg: str) -> str:
    msg = error_msg.upper()
    if "RESOURCE_EXHAUSTED" in msg or "429" in msg or "QUOTA" in msg:
        return "⚠️ AI quota limit reached — please try again in a few minutes."
    if "503" in msg or "UNAVAILABLE" in msg:
        return "⚠️ AI service is temporarily unavailable — please try again shortly."
    if "401" in msg or "403" in msg or "PERMISSION" in msg or "API_KEY" in msg:
        return "⚠️ AI service configuration error — please contact the admin."
    return "⚠️ Something went wrong tailoring your resume — please resubmit the job description."


def error_node(state: TailorState) -> dict[str, Any]:
    error_msg = state.get("last_error") or "Unknown error"
    logger.error(f"error_node job_id={state.get('job_id')} error={error_msg!r}")

    try:
        get_slack().chat_postMessage(
            channel=settings.slack_channel_id,
            text=_user_friendly_error(error_msg),
        )
    except Exception as exc:
        logger.error(f"error_node_slack_failed error={exc}")

    try:
        with SessionLocal() as db:
            job = db.get(Job, state.get("job_id"))
            if job:
                job.status = JobStatus.failed.value
                db.commit()
    except Exception as exc:
        logger.error(f"error_node_db_failed error={exc}")

    try:
        trace_id = state.get("langfuse_trace_id", "")
        if trace_id:
            get_langfuse().create_score(trace_id=trace_id, name="error", value=0.0)
    except Exception as exc:
        logger.warning(f"error_node_langfuse_failed error={exc}")

    return {"status": "failed"}
