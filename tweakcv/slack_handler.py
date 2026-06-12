from __future__ import annotations

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from langgraph.types import Command
from loguru import logger
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler

from tweakcv.clients import get_langfuse, get_slack
from tweakcv.db import Job, JobStatus, SessionLocal, init_db
from tweakcv.graph import build_checkpointer, build_graph
from tweakcv.harness_loader import load_harnesses
from tweakcv.runner import run_job, stale_sweep
from tweakcv.settings import settings

_HARNESS_PATH = Path(__file__).parent / "harness.json"

# Minimum JD length to avoid triggering on short channel messages
_JD_MIN_CHARS = 100

_graph: Any = None
_checkpointer: Any = None


def _get_graph() -> Any:
    global _graph, _checkpointer
    if _graph is None:
        _checkpointer = build_checkpointer()
        _graph = build_graph(_checkpointer)
        logger.info("graph_initialised")
    return _graph


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_harnesses(str(_HARNESS_PATH))
    init_db()
    _get_graph()
    stale_sweep(get_slack(), _get_graph())
    logger.info(f"tweakcv_ready min_chars={_JD_MIN_CHARS} channel={settings.slack_channel_id}")
    yield


bolt_app = App(
    token=settings.slack_bot_token.get_secret_value(),
    signing_secret=settings.slack_signing_secret.get_secret_value(),
)
handler = SlackRequestHandler(bolt_app)
app = FastAPI(lifespan=_lifespan)

# thread_ts → job_id: tracks edit requests waiting for a Slack thread reply
_pending_edit_registry: dict[str, int] = {}
_registry_lock = threading.Lock()


def _resume_graph(job_id: int, feedback: str) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            logger.error(f"resume_graph_job_not_found job_id={job_id}")
            return
        thread_id = job.thread_id

    config = {"configurable": {"thread_id": thread_id}}
    logger.info(f"resume_graph_resuming job_id={job_id} feedback={feedback!r}")
    try:
        _get_graph().invoke(Command(resume=feedback), config=config)
    except Exception as exc:
        logger.error(f"resume_graph_failed job_id={job_id} error={exc}")


def _log_user_approval(job_id: int, value: float, comment: str) -> None:
    try:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            trace_id = job.langfuse_trace_id if job else None
        if trace_id:
            get_langfuse().create_score(
                trace_id=trace_id, name="user_approval", value=value, comment=comment
            )
    except Exception as exc:
        logger.warning(f"log_user_approval_failed error={exc}")


def _mark_rejected(job_id: int) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job:
            job.status = JobStatus.rejected.value
            db.commit()


@bolt_app.action("approve_resume")
def handle_approve(ack: Any, body: dict[str, Any]) -> None:
    ack()
    job_id = int(body["actions"][0]["value"])
    logger.info(f"handle_approve job_id={job_id}")
    _resume_graph(job_id, "approve")


@bolt_app.action("edit_resume")
def handle_edit(ack: Any, body: dict[str, Any], say: Any) -> None:
    ack()
    job_id = int(body["actions"][0]["value"])
    thread_ts: str = body["message"]["ts"]
    logger.info(f"handle_edit job_id={job_id} thread_ts={thread_ts}")
    with _registry_lock:
        _pending_edit_registry[thread_ts] = job_id

    # Replace action buttons with a pending indicator while waiting for the thread reply.
    # Keep all resume content blocks; only remove the actions block.
    current_blocks: list[dict[str, Any]] = body.get("message", {}).get("blocks", [])
    pending_blocks = [b for b in current_blocks if b.get("type") != "actions"]
    pending_blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "✏️ _Edit in progress — reply in thread with your changes_",
                }
            ],
        }
    )
    try:
        get_slack().chat_update(
            channel=settings.slack_channel_id,
            ts=thread_ts,
            text="Edit in progress — reply in thread with your changes",
            blocks=pending_blocks,
        )
    except Exception as exc:
        logger.warning(f"handle_edit_disable_buttons_failed error={exc}")

    say(text="What would you like to change?", thread_ts=thread_ts)


@bolt_app.action("reject_resume")
def handle_reject(ack: Any, body: dict[str, Any]) -> None:
    ack()
    job_id = int(body["actions"][0]["value"])
    thread_ts: str = body["message"]["ts"]
    logger.info(f"handle_reject job_id={job_id}")
    _log_user_approval(job_id, 0.0, "reject")
    _mark_rejected(job_id)
    try:
        get_slack().chat_update(
            channel=settings.slack_channel_id,
            ts=thread_ts,
            text="❌ Rejected — resume discarded",
            blocks=[
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "❌ *Rejected* — submit a new job description to start fresh.",
                        }
                    ],
                }
            ],
        )
    except Exception as exc:
        logger.warning(f"handle_reject_message_update_failed error={exc}")
    _resume_graph(job_id, "reject")


@bolt_app.event("message")
def handle_message(body: dict[str, Any]) -> None:
    event = body.get("event", {})
    text: str = event.get("text", "")
    bot_id = event.get("bot_id")
    subtype = event.get("subtype")
    thread_ts: str | None = event.get("thread_ts")
    ts: str = event.get("ts", "")

    # Thread reply in an active edit session
    with _registry_lock:
        pending_job_id: int | None = (
            _pending_edit_registry.pop(thread_ts)
            if thread_ts and thread_ts in _pending_edit_registry and not bot_id
            else None
        )

    if thread_ts and not bot_id and pending_job_id is not None:
        logger.info(f"message_edit_reply job_id={pending_job_id} text={text!r}")
        _resume_graph(pending_job_id, f"edit:{text}")
        return

    if thread_ts:
        return

    # Ignore bot messages and subtypes (joins, topic changes, etc.)
    if bot_id or subtype:
        return

    # Top-level user message — treat as new JD submission
    if len(text) < _JD_MIN_CHARS:
        logger.debug(f"message_too_short chars={len(text)}")
        get_slack().chat_postMessage(
            channel=settings.slack_channel_id,
            thread_ts=ts,
            text=f"Paste a job description (at least {_JD_MIN_CHARS} characters) and I'll tailor your resume.",
        )
        return

    logger.info(f"message_jd_received chars={len(text)}")
    loading_resp = get_slack().chat_postMessage(
        channel=settings.slack_channel_id,
        text="⏳ Tailoring your resume — this takes about a minute...",
    )
    loading_ts: str = loading_resp.get("ts", "")
    threading.Thread(target=_run_job_background, args=(text, loading_ts), daemon=True).start()


def _run_job_background(jd_text: str, loading_ts: str = "") -> None:
    try:
        job_id = run_job(jd_text, _get_graph(), loading_ts=loading_ts)
        logger.info(f"job_completed job_id={job_id}")
    except Exception:
        logger.exception("job_failed")
        if loading_ts:
            import contextlib

            with contextlib.suppress(Exception):
                get_slack().chat_update(
                    channel=settings.slack_channel_id,
                    ts=loading_ts,
                    text="❌ Something went wrong tailoring your resume — please resubmit.",
                    blocks=[],
                )


@app.post("/slack/events")
async def slack_events(req: Request) -> Any:
    return await handler.handle(req)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
