# CLI Contract

**File**: `tweakcv/main.py` | **Entrypoint**: `python main.py`

## Usage

```
python main.py <JD_TEXT_OR_PATH> [--file]
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `JD_TEXT_OR_PATH` | Yes | Job description as inline text, or a file path when `--file` is set |

## Options

| Option | Type | Description |
|--------|------|-------------|
| `--file` | flag | Treat `JD_TEXT_OR_PATH` as a file path; read JD text from that file |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Graph reached `interrupt()` — Slack review message sent successfully |
| `1` | Startup validation failure (missing env vars, unreadable `base_resume.json`, Slack unreachable) |
| `2` | Graph hard-failed after all node retries exhausted |

## Examples

```bash
# Inline job description
python main.py "We are looking for a Senior Python Engineer..."

# From file
python main.py /tmp/jd.txt --file

# From clipboard (macOS)
python main.py "$(pbpaste)"
```

## Startup Sequence

When invoked, `main.py` performs in order:
1. `load_dotenv()` — load `.env`
2. `load_harnesses("harness.json")` — parse harness config once
3. `init_db()` — create SQLite tables if not exist
4. Validate required env vars + `base_resume.json` readable + Slack channel pingable
5. `stale_sweep(db, graph, slack_client)` — one-shot: expire `pending` jobs older than 24h
6. Parse JD input (inline or `--file`)
7. Create `Job` row in `tailorcv.db`; generate `thread_id = str(uuid4())`
8. Create Langfuse trace; store `trace.id` in `Job.langfuse_trace_id`
9. `graph.invoke(initial_state, config={"configurable": {"thread_id": thread_id}})` — blocks until `interrupt()`

The CLI process **blocks** at step 9 until the LangGraph graph reaches `await_feedback_node` and calls `interrupt()`. Once paused, the CLI prints a confirmation message and exits with code `0`. The `slack_handler.py` FastAPI server (running in Docker) handles all subsequent Slack interactions.
