# Research: Resume Tailoring CLI

**Feature**: `002-resume-tailoring-cli` | **Date**: 2026-06-01

## Technology Decisions

### LangGraph + langchain-google-genai

- **Decision**: LangGraph for workflow orchestration (HITL, checkpointing, conditional routing); `langchain-google-genai` for Gemini LLM calls using `.with_structured_output(PydanticModel)`
- **Rationale**: LangGraph is part of the LangChain ecosystem — this satisfies the "Langchain" requirement from `docs/TRD.md`. `.with_structured_output()` eliminates manual JSON parsing and provides automatic retry on schema mismatch. Gemini SDK transport-layer auto-retry (4×, exp backoff) is preserved.
- **Alternatives considered**: Raw `google-generativeai` SDK — no Pydantic structured output, no LangGraph integration; would require manual JSON parsing and schema validation in every node.

### Langfuse Prompt Management

- **Decision**: `langfuse_client.get_prompt(id)` at runtime as primary source; fallback to `harness.json["system_prompt"]` on any exception (network error, service down)
- **Rationale**: SDK TTL-caches prompts locally — no per-call latency after warmup. Every Langfuse trace auto-links to the exact prompt version used, enabling A/B comparison without code changes or restarts.
- **Alternatives considered**: Prompts only in `harness.json` — no versioning, no per-trace version linking, no A/B capability.

### HITL: `interrupt()` + `SqliteSaver`

- **Decision**: LangGraph's `interrupt()` in `await_feedback_node`; graph state serialised to `checkpoints.db` via `SqliteSaver`; resumed via `graph.invoke(Command(resume=feedback), config={"configurable": {"thread_id": ...}})`
- **Rationale**: Native LangGraph HITL pattern. State survives process restarts — if the app crashes between CLI invocation and Slack response, resuming from checkpoint is transparent. No polling, no external queue.
- **Alternatives considered**: asyncio Event / queue — does not survive restarts; Redis pubsub — unnecessary external service for a single-user tool.

### Slack Architecture: Bolt + FastAPI

- **Decision**: `SlackRequestHandler` from `slack_bolt.adapter.fastapi` bridges both frameworks under a single FastAPI app serving `/slack/events`
- **Rationale**: Bolt handles Slack signature verification, event type routing, and `ack()` (required within 3 seconds). FastAPI manages the HTTP server lifecycle. Standard documented pattern for Bolt + async frameworks.
- **Alternatives considered**: Flask — synchronous, no native async support; raw HTTP — loses Bolt's request verification and action routing.

### Edit Routing: `edit_node → notify_node`

- **Decision**: `edit_node` applies targeted changes to the existing `tailored_resume` and routes back to `notify_node`, not `tailor_node`
- **Rationale**: Targeted edits preserve the user's approved context from prior iterations. Re-running `tailor_node` would discard all previous refinements and regenerate from scratch. Matches the TRD architecture diagram exactly.
- **Alternatives considered**: `edit → tailor` — would produce a completely new resume on every edit request, ignoring the user's prior feedback iterations.

### Two SQLite DB Files

- **Decision**: `tailorcv.db` for app data (SQLAlchemy models); `checkpoints.db` for LangGraph `SqliteSaver`
- **Rationale**: LangGraph `SqliteSaver` manages its own schema (`checkpoints`, `checkpoint_writes` tables). Keeping it separate from app tables avoids schema collision and allows independent backup/inspection of each.
- **Alternatives considered**: Single DB file — schema collisions possible if LangGraph adds tables; harder to inspect app data independently.

### Stale Sweep: Startup-Only, No Scheduler

- **Decision**: Synchronous `stale_sweep()` in `main.py` startup, completes in < 1 second
- **Rationale**: Personal single-user tool. If the app is running, cleanup runs. APScheduler or background threads add complexity (daemon threads, signal handling, cross-thread DB sessions) with no benefit for a tool that runs on-demand.
- **Alternatives considered**: APScheduler — background thread complexity; cron job — external dependency; no sweep — stale jobs linger forever.

### Docker: Two Named Volumes

- **Decision**: `tweakcv_data` for `/app/data` (SQLite + checkpoints); `tweakcv_output` for `/app/output` (PDFs)
- **Rationale**: Separates persistent data from exported artifacts. Both survive `docker compose down`. WeasyPrint system library requirements (pango, gdk-pixbuf, fonts) are the primary reason Docker is required — they conflict with macOS system libraries.
- **Alternatives considered**: Bind mounts — less portable; single volume — mixes DB files with user-facing PDF output.

## Resolved Clarifications

| Topic | Resolution |
|-------|-----------|
| "Langchain" in user request | LangGraph (part of LangChain ecosystem) + `langchain-google-genai` for LLM calls |
| Slack bot scope | Full bot: button interactions (approve/edit/reject) + `message.channels` event listener for edit thread replies |
| Edit routing | `edit_node → notify_node` (targeted edits, not full regeneration via `tailor_node`) |
| Two DB files vs one | Two: `tailorcv.db` + `checkpoints.db` — separate to avoid schema collision |
| PDF filename | `RozaRusskikh_{Role}_2026.pdf` (from PRD constraints) |
| Langfuse span vs trace | One trace per CLI run; nodes attach `span()` calls within that trace; `score()` attached to the root trace |
