---
name: project-security-patterns
description: Confirmed secure patterns and recurring anti-patterns found in the tweak-cv codebase during initial security review
metadata:
  type: project
---

## Confirmed Secure Patterns (preserve these)

- **Slack HMAC verification**: Delegated entirely to `slack_bolt.App(signing_secret=...)` via `SlackRequestHandler`. Bolt handles timing-safe comparison and replay window internally. Do not add manual HMAC checks on top.
- **SecretStr usage**: All secrets (`gemini_api_key`, `slack_bot_token`, `slack_signing_secret`, `langfuse_public_key`, `langfuse_secret_key`) are `SecretStr` in `settings.py`. `.get_secret_value()` is called only at client construction in `clients.py` and `harness_loader.py`.
- **Jinja2 autoescape**: `Environment(autoescape=True)` is set in `finalize.py` — HTML output is safe from XSS/template injection.
- **Pydantic structured LLM output**: All LLM calls use `.with_structured_output(PydanticModel)` — LLM responses are validated by schema before use.
- **SQLAlchemy ORM**: All DB access uses ORM (`db.get(Job, job_id)`, `db.query(Job).filter(...)`) — no raw SQL string interpolation found.
- **Thread-safe edit registry**: `_pending_edit_registry` in `slack_handler.py` is guarded by `threading.Lock()`.

## Recurring Anti-Patterns Found

- **Hardcoded host path in docker-compose.yml**: `docker-compose.yml` line 11 contains `/Users/rozaliiarusskikh/Desktop/resumes:/app/output/resumes` — a developer's absolute local path committed to source. This is a privacy/portability issue but not a credential leak.
- **uv:latest in Dockerfile**: `COPY --from=ghcr.io/astral-sh/uv:latest` uses a floating tag — supply chain risk. Should pin to a digest.
- **Unvalidated job_id from Slack body**: `int(body["actions"][0]["value"])` in action handlers — no bounds/existence check before DB lookup. However the DB lookup returns `None` if not found, so exploitation impact is limited (no IDOR for different users since it's single-user).
- **Prompt injection surface**: `edit_node` passes raw Slack thread text directly as `edit_request` into an LLM prompt. This is an inherent single-user design trade-off but should be documented.
- **DATABASE_URL logged**: `init_db()` logs the full `database_url` value at INFO level. In Docker this is `sqlite:////app/data/tailorcv.db` (not a secret), but the pattern should be noted.
- **`db.py` logs DATABASE_URL**: `logger.info(f"db_initialised url={settings.database_url}")` — acceptable for SQLite but would leak credentials if ever migrated to Postgres.

## Safety-Critical Functions (require extra scrutiny on any change)

- `tweakcv/nodes/score.py::_detect_new_entities()` — hallucination guard
- `tweakcv/graph.py::route_feedback()` — HITL routing logic
- `tweakcv/slack_handler.py` — Slack signature verification path

**Why:** Per CLAUDE.md, these are explicitly listed as safety-critical. Any regression here could allow hallucinated content to be approved or HITL to be bypassed.
