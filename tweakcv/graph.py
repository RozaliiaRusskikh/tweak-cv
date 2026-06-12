from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from loguru import logger

from tweakcv.settings import settings
from tweakcv.state import TailorState


def build_checkpointer() -> SqliteSaver:
    """Derive the checkpoint DB path from DATABASE_URL and return a SqliteSaver."""
    url = settings.database_url
    # Handle sqlite:////abs/path (4 slashes = absolute) and sqlite:///rel/path (3 = relative)
    if url.startswith("sqlite:////"):
        db_path = Path("/" + url[len("sqlite:////") :])
    elif url.startswith("sqlite:///"):
        db_path = Path(url[len("sqlite:///") :])
    else:
        db_path = Path(url)
    checkpoint_path = db_path.parent / "checkpoints.db"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(checkpoint_path), check_same_thread=False)
    return SqliteSaver(conn)


def route_feedback(state: TailorState) -> str:
    """Route after await_feedback_node based on feedback value and iteration count."""
    feedback = state.get("feedback", "")
    status = state.get("status", "")

    if status == "failed":
        return "error"
    if feedback == "expired" or status == "expired":
        return "expired"
    if feedback == "reject":
        return "reject"
    if feedback == "approve":
        return "approve"
    if state.get("iteration", 0) >= 4:
        logger.warning("route_max_iterations", iteration=state.get("iteration"))
        return "reject"
    if feedback.startswith("edit:") or feedback == "edit":
        return "edit"
    return "approve"


def _route_or_error(state: TailorState) -> str:
    """After tailor/edit: check if node reported a failure before continuing."""
    if state.get("status") == "failed":
        return "error"
    return "ok"


def build_graph(checkpointer: SqliteSaver) -> CompiledStateGraph[Any, Any, Any]:
    # Import nodes here to avoid circular imports at module load time
    from tweakcv.nodes.analyze import analyze_node
    from tweakcv.nodes.await_feedback import await_feedback_node
    from tweakcv.nodes.edit import edit_node
    from tweakcv.nodes.error import error_node
    from tweakcv.nodes.finalize import finalize_node
    from tweakcv.nodes.notify import notify_node
    from tweakcv.nodes.tailor import tailor_node

    g: StateGraph = StateGraph(TailorState)  # type: ignore[type-arg]

    g.add_node("analyze", analyze_node)
    g.add_node("tailor", tailor_node)
    g.add_node("notify", notify_node)
    g.add_node("await_feedback", await_feedback_node)
    g.add_node("edit", edit_node)
    g.add_node("error", error_node)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "analyze")
    g.add_conditional_edges(
        "analyze",
        _route_or_error,
        {"ok": "tailor", "error": "error"},
    )

    g.add_conditional_edges(
        "tailor",
        _route_or_error,
        {"ok": "notify", "error": "error"},
    )

    g.add_edge("notify", "await_feedback")

    g.add_conditional_edges(
        "await_feedback",
        route_feedback,
        {
            "approve": "finalize",
            "edit": "edit",
            "reject": END,
            "expired": END,
            "error": "error",
        },
    )

    g.add_conditional_edges(
        "edit",
        _route_or_error,
        {"ok": "notify", "error": "error"},
    )

    g.add_edge("finalize", END)
    g.add_edge("error", END)

    return g.compile(checkpointer=checkpointer)
