# Tasks: Resume Tailoring CLI

**Input**: Design documents from `specs/resume-tailoring-cli/`

**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/ ✅

**Tests**: Required — CLAUDE.md mandates tests for all critical paths. Unit tests use in-memory SQLite; all LLM/Slack/Langfuse calls are mocked.

**Format**: `- [x] [ID] [P?] [Story?] Description — tweakcv/path/to/file.py`

---

## Phase 1: Setup (Project Scaffold)

**Purpose**: Create all static files — no logic yet. After this phase `pip install` works and the container builds.

- [x] T001 Create `tweakcv/` package directory with `__init__.py` and subdirectories: `nodes/`, `tests/nodes/`, `tests/`, `evals/`, `templates/`, `output/` (gitkeep)
- [x] T002 Write `pyproject.toml`: all dependencies (`langgraph`, `langchain-google-genai`, `langfuse`, `slack-bolt`, `fastapi`, `uvicorn`, `sqlalchemy`, `weasyprint`, `jinja2`, `python-dotenv`, `pydantic[email]`, `click`, `loguru`), dev deps (`pytest`, `pytest-mock`, `ruff`, `mypy`), ruff + mypy config — `pyproject.toml`
- [x] T003 [P] Write `.env.example` with all 8 vars: `GEMINI_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_CHANNEL_ID`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `DATABASE_URL` — `.env.example`
- [x] T004 [P] Write `harness.json` with 4 complete harness entries (`analyze-jd` gemini-2.0-flash 30s, `tailor-resume` gemini-2.0-flash 60s, `edit-resume` gemini-2.5-flash 60s, `quality-judge` gemini-2.5-flash 30s) — `tweakcv/harness.json`
- [x] T005 [P] Write `base_resume.json` with the correct schema: `name`, `summary`, `experience[]` (company/role/dates/bullets), `skills[]`, `education[]` (institution/degree/year) — `tweakcv/base_resume.json`
- [x] T006 [P] Write `templates/resume.html`: Jinja2 template with inline CSS for WeasyPrint — `tweakcv/templates/resume.html`
- [x] T007 Write `Dockerfile`: `python:3.13-slim` base; WeasyPrint system libs; uv; `CMD uvicorn tweakcv.slack_handler:app` — `Dockerfile`
- [x] T008 Write `docker-compose.yml`: service on port `3000`; `env_file: .env`; volumes `tweakcv_data:/app/data`, `tweakcv_output:/app/output` — `docker-compose.yml`

**Checkpoint**: ✅ `uv install` succeeds; `docker compose build` succeeds

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data layer, schemas, and harness loader. Everything in Phase 3+ depends on these.

**⚠️ CRITICAL**: No user story work starts until this phase is complete and its tests pass.

- [x] T009 Write `tweakcv/config.py`: `Settings(BaseSettings)` with `SecretStr` for all API keys/tokens — `tweakcv/settings.py`
- [x] T010 Write `JobStatus` `Enum` in `tweakcv/db.py`: values `pending`, `approved`, `rejected`, `expired`, `failed` — `tweakcv/db.py`
- [x] T011 Write `Job` SQLAlchemy model in `tweakcv/db.py`: all 10 columns with `Mapped[]` typed annotations — `tweakcv/db.py`
- [x] T012 Write `ResumeVersion` SQLAlchemy model in `tweakcv/db.py`: `Mapped[]` types; FK to `jobs(id)` with `ON DELETE CASCADE` — `tweakcv/db.py`
- [x] T013 Write `init_db()`, `get_db()`, `SessionLocal`, and two `Index()` objects in `tweakcv/db.py` — `tweakcv/db.py`
- [x] T014 [P] Write `ExperienceEntry`, `EducationEntry`, `JDAnalysisOutput` Pydantic models — `tweakcv/schemas.py`
- [x] T015 [P] Write `TailoredResumeOutput`, `QualityJudgeOutput`, `ScoreResult` Pydantic models — `tweakcv/schemas.py`
- [x] T016 Write `load_harnesses(path: str)` — `tweakcv/harness_loader.py`
- [x] T017 Write `get_prompt(harness_id: str) -> str` with Langfuse-primary / harness.json-fallback — `tweakcv/harness_loader.py`
- [x] T018 Write `get_llm(harness_id: str) -> ChatGoogleGenerativeAI` — `tweakcv/harness_loader.py`
- [x] T019 Write `TailorState` `TypedDict` with all 16 fields — `tweakcv/state.py`
- [x] T020 Write `build_graph(checkpointer)` and `route_feedback()` — `tweakcv/graph.py`
- [x] T021 [P] Write `tests/test_db.py`: tables created; `JobStatus` values; cascade delete — `tests/test_db.py`
- [x] T022 [P] Write `tests/test_schemas.py`: validation, round-trip JSON, `needs_retry` logic — `tests/test_schemas.py`
- [x] T023 [P] Write `tests/test_harness_loader.py`: parse JSON; Langfuse primary; fallback on exception — `tests/test_harness_loader.py`

**Checkpoint**: ✅ `uv run pytest tests/test_db.py tests/test_schemas.py tests/test_harness_loader.py` — all pass

---

## Phase 3: User Story 1 — Tailor Resume and Send for Review (Priority: P1) 🎯 MVP

**Goal**: CLI accepts a JD → LangGraph tailors base resume → Slack message sent with scores and Approve/Edit/Reject buttons.

**Independent Test**: `python main.py "Senior Python Engineer at Acme..."` → Slack message appears within 2 min with resume text, `keyword_coverage`, `no_hallucination`, and three action buttons.

### Tests — User Story 1

- [x] T024 [P] [US1] `kw_coverage` calculation tests — `tests/nodes/test_score.py`
- [x] T025 [P] [US1] `_detect_new_entities()` hallucination tests — `tests/nodes/test_score.py`
- [x] T026 [P] [US1] `needs_retry` and quality judge conditional tests — `tests/nodes/test_score.py`
- [x] T027 [P] [US1] `analyze_node()` returns partial state (mocked LLM) — `tests/nodes/test_analyze.py`
- [x] T028 [P] [US1] `route_feedback()` approve/reject routing — `tests/test_graph.py`
- [x] T029 [P] [US1] `route_feedback()` edit routing + hard stop at iteration 4 — `tests/test_graph.py`
- [x] T030 [P] [US1] `route_feedback()` expired routing — `tests/test_graph.py`

### Implementation — User Story 1

- [x] T031 Write `compute_keyword_coverage()`, `_detect_new_entities()` — `tweakcv/nodes/score.py`
- [x] T032 Write `compute_edit_fidelity()` — `tweakcv/nodes/score.py`
- [x] T033 Write `_call_quality_judge()` — `tweakcv/nodes/score.py`
- [x] T034 Write `score()` orchestrator + `_attach_langfuse_scores()` — `tweakcv/nodes/score.py`
- [x] T035 Write `analyze_node()` — `tweakcv/nodes/analyze.py`
- [x] T036 Write `tailor_node()` with inline scoring — `tweakcv/nodes/tailor.py`
- [x] T037 Silent retry block when `scores.needs_retry` — `tweakcv/nodes/tailor.py`
- [x] T038 Write `_build_blocks()`, `_score_text()` — `tweakcv/nodes/notify.py`
- [x] T039 Action blocks with Edit button conditional on `iteration < 4` — `tweakcv/nodes/notify.py`
- [x] T040 Write `notify_node()` (post + update Slack + update DB) — `tweakcv/nodes/notify.py`
- [x] T041 Write `await_feedback_node()` with `interrupt()` + iteration ≥ 4 hard stop — `tweakcv/nodes/await_feedback.py`
- [x] T042 Write `route_feedback()` all branches — `tweakcv/graph.py`
- [x] T043 Complete `build_graph()` with all edges + conditional routing — `tweakcv/graph.py`
- [x] T044 Write `error_node()` — `tweakcv/nodes/error.py`
- [x] T045 Startup validation + `load_harnesses` + `init_db` — `tweakcv/main.py`
- [x] T046 Write `stale_sweep()` — `tweakcv/main.py`
- [x] T047 Write `@click.command()` with arg + `--file` flag — `tweakcv/main.py`
- [x] T048 Job row creation + Langfuse trace + initial TailorState — `tweakcv/main.py`
- [x] T049 `graph.invoke()` call + exit codes — `tweakcv/main.py`

**Checkpoint**: Tests pass ✅ — Slack smoke test pending real credentials

---

## Phase 4: User Story 2 — Approve and Export as PDF (Priority: P2)

**Goal**: User clicks Approve in Slack → PDF saved to `output/` → Slack confirms with file path.

**Independent Test**: Click Approve on the Slack message; verify `output/RozaRusskikh_*_2026.pdf` exists; `jobs.status='approved'` in DB; Langfuse trace has `user_approval=1.0`.

### Tests — User Story 2

- [x] T050 [P] [US2] `finalize_node()` creates PDF, updates DB, logs `user_approval=1.0` — `tests/nodes/test_finalize.py`
- [x] T051 [P] [US2] Slack HMAC signature validation tests — `tests/test_slack_handler.py`

### Implementation — User Story 2

- [x] T052 Write `_render_html()` — `tweakcv/nodes/finalize.py`
- [x] T053 Write `_export_pdf()` with lazy `weasyprint` import — `tweakcv/nodes/finalize.py`
- [x] T054 Write `finalize_node()` — `tweakcv/nodes/finalize.py`
- [x] T055 Write FastAPI `app` + `SlackRequestHandler` — `tweakcv/slack_handler.py`
- [x] T056 Write `_resume_graph()` helper — `tweakcv/slack_handler.py`
- [x] T057 Write `@bolt_app.action("approve_resume")` handler — `tweakcv/slack_handler.py`

**Checkpoint**: Tests pass ✅ — PDF smoke test pending real credentials

---

## Phase 5: User Story 3 — Request Edits via Slack Thread (Priority: P3)

**Goal**: User clicks Edit → bot asks what to change → user replies → updated resume posted in thread; max 3 iterations.

**Independent Test**: Click Edit; type change request; confirm updated resume in thread within 90 sec; `resume_versions` has new row.

### Tests — User Story 3

- [x] T058 [P] [US3] `edit_node()` increments iteration, saves ResumeVersion, clears feedback — `tests/nodes/test_edit.py`
- [x] T059 [P] [US3] `compute_edit_fidelity()` returns 1.0 for identical, varies for changes — `tests/nodes/test_score.py`
- [x] T060 [P] [US3] Block Kit action buttons conditional on iteration — `tests/nodes/test_notify.py`

### Implementation — User Story 3

- [x] T061 `compute_edit_fidelity()` already in score.py — `tweakcv/nodes/score.py`
- [x] T062 Write `edit_node()` — `tweakcv/nodes/edit.py`
- [x] T063 Iteration warning block (iteration == 3) in `notify_node` — `tweakcv/nodes/notify.py`
- [x] T064 Iteration ≥ 4 hard stop in `await_feedback_node` — `tweakcv/nodes/await_feedback.py`
- [x] T065 `_pending_edit_registry` module-level dict — `tweakcv/slack_handler.py`
- [x] T066 `@bolt_app.action("edit_resume")` handler — `tweakcv/slack_handler.py`
- [x] T067 `@bolt_app.event("message")` handler — `tweakcv/slack_handler.py`

**Checkpoint**: Tests pass ✅

---

## Phase 6: User Story 4 — Reject or Let It Expire (Priority: P4)

**Goal**: User clicks Reject → nothing saved; OR 24h passes → message auto-expires.

### Tests — User Story 4

- [x] T068 [P] [US4] HMAC signature tests in test_slack_handler.py — `tests/test_slack_handler.py`
- [x] T069 [P] [US4] `stale_sweep()` expires old job, skips recent job — `tests/test_main.py`

### Implementation — User Story 4

- [x] T070 Write `@bolt_app.action("reject_resume")` handler — `tweakcv/slack_handler.py`
- [x] T071 `route_feedback("reject")` → END; `route_feedback("expired")` → END — `tweakcv/graph.py` ✅
- [x] T072 `stale_sweep()` handles zero stale jobs gracefully — `tweakcv/main.py` ✅

**Checkpoint**: Tests pass ✅

---

## Phase 7: Observability, Evals & Docker Polish

**Purpose**: Offline eval runner, lint, type checks, Docker verification.

- [x] T073 [P] Write `evals/dataset.json` with 3 labelled examples — `evals/dataset.json`
- [x] T074 Write `evals/run_evals.py` standalone offline runner — `evals/run_evals.py`
- [x] T075 [P] `uv run ruff check tweakcv/` — all checks pass ✅
- [ ] T076 [P] Run `uv run mypy --strict tweakcv/`; fix all type errors
- [x] T077 [P] `uv run pytest` — 58/58 tests pass ✅
- [ ] T078 Docker smoke test: `docker compose up --build`; run happy path; verify PDF in volume

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; all T001–T008 can run in parallel
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories; T009–T020 sequential within DB layer; T021–T023 test tasks can run in parallel with T009–T020
- **Phase 3 (US1)**: Depends on Phase 2 complete — **MVP**
- **Phase 4 (US2)**: Depends on Phase 3 complete (needs working graph + Slack notify)
- **Phase 5 (US3)**: Depends on Phase 4 complete (needs `slack_handler.py` base)
- **Phase 6 (US4)**: Depends on Phase 5 complete (same handler)
- **Phase 7 (Polish)**: Depends on Phase 6 complete

---

## Notes

- `[P]` = can run in parallel with other `[P]` tasks in the same phase (different files, no shared deps)
- `[US1]–[US4]` = maps task to user story for traceability
- All DB tests use `sqlite:///:memory:` — never touch `tailorcv.db`
- All LLM, Slack, Langfuse calls in tests use `unittest.mock`
- `_detect_new_entities()` and `route_feedback()` are safety-critical — any change requires updated tests (per CLAUDE.md)
- T076 (mypy --strict) and T078 (Docker smoke test) require real env and system libs — pending manual verification
