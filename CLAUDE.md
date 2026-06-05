<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at `specs/resume-tailoring-cli/plan.md`
<!-- SPECKIT END -->

## Before Writing Code

- See README.md for project overview.
- Read the relevant contract in `specs/resume-tailoring-cli/contracts/` before touching any router, schema, or response model.
- Examine existing code for similar functionality, style, and patterns.
- Plan the simplest solution that meets requirements and fits the existing architecture.
- Check official docs when needed: [FastAPI](https://fastapi.tiangolo.com), [Python 3.13](https://docs.python.org/3.13/), [Pydantic v2](https://docs.pydantic.dev/), [SQLAlchemy 2.0](https://docs.sqlalchemy.org/), [LangGraph](https://langchain-ai.github.io/langgraph/), [Langfuse](https://langfuse.com/docs), [Slack Bolt](https://slack.dev/bolt-python/), [WeasyPrint](https://doc.courtbouillon.org/weasyprint/).

## Stack

Python 3.13 · FastAPI · SQLAlchemy 2.0 (sync) · SQLite · LangGraph · `langchain-google-genai` · Langfuse · Slack Bolt · WeasyPrint · Jinja2 · Click

**Package manager**: `uv`. Always use `uv run` and `uv add`.

## Code Quality

Run all three before committing:

```bash
uv run ruff format .        # auto-format
uv run ruff check .         # lint
uv run mypy --strict .      # type check
```

- Use `X | None` not `Optional[X]`, `list[T]` not `List[T]`, `dict[K, V]` not `Dict[K, V]`.
- Use Pydantic v2 models for all schemas.
- Store secrets (API keys, tokens) in `.env`; access via Pydantic `Settings`. Use `SecretStr` for sensitive values and call `.get_secret_value()` before use.

## Security

- Never commit `.env` — it is in `.gitignore`. Verify before staging.
- Never hardcode credentials, URLs, or secrets anywhere in the codebase.

## Architecture

- Nodes → `db.get_db()`. No business logic in Slack handlers or CLI entrypoint.
- DB session injection only via `get_db()`. No direct access to the session factory in nodes or handlers.

## Database (SQLAlchemy 2.0 sync · SQLite)

- Use `Mapped[]` typed columns. The SQLAlchemy 2.0 typed API (`Mapped[str]`, `Mapped[int | None]`) is required. Legacy `Column()` without types is not allowed.
- `Job.status` must be enforced as a Python `Enum`. Valid states: `pending → approved / rejected / expired / failed`. Validate at the application layer — do not allow freeform strings.

## Logging

Use `loguru` for all logging. Never use the stdlib `logging` module directly.

```python
from loguru import logger

logger.info("...")
logger.error("...")
```

## Testing

- Test runner: `pytest`. Run with `uv run pytest`.
- Tests live in `tests/`. Mirror the source structure: `tests/nodes/`, `tests/test_db.py`, etc.
- Offline eval runner at `evals/run_evals.py` for prompt benchmarking — not a substitute for unit tests.
- A feature is not done until its critical path has a test.

### Must-have unit tests (pure logic, no network)

| Module | What to cover |
|---|---|
| `nodes/score.py` | `kw_coverage` calculation; `_detect_new_entities()` (hallucination guard); `needs_retry` trigger (`kw < 0.5`); `quality_judge` condition (`0.4 ≤ kw ≤ 0.6`); `edit_fidelity` |
| `graph.py` | `route_feedback()` — all branches: `"approve"`, `"reject"`, `"edit:..."`, `"expired"` |
| `harness_loader.py` | `load_harnesses()` parses valid JSON; `get_prompt()` falls back to `harness["system_prompt"]` when Langfuse raises |
| `slack_handler.py` | HMAC signature verification (valid sig passes, bad sig fails, replay window rejected) |
| `schemas.py` | Pydantic validation: required fields, type coercion, rejection of invalid input |
| `db.py` | `init_db()` creates both tables; Job status transitions; ResumeVersion cascade delete on Job delete |

### Rules

- Use an in-memory SQLite database for all DB tests (`sqlite:///:memory:`). Never touch `tailorcv.db` in tests.
- Mock all LLM calls (`langchain-google-genai`), Slack API calls, and Langfuse calls — test logic, not the network.
- `_detect_new_entities()` and `route_feedback()` are safety-critical — any change to them requires updated tests.
