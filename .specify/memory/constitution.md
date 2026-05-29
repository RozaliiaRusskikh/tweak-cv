<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 1.0.1 (patch)
Changed:
  - II. Harness-First Prompts: Langfuse Prompt Management is now primary source;
    harness.json system_prompt field is the offline/unavailable fallback.
  - Technology Constraints: Observability row updated to include prompt management.
-->

# TweakCV Constitution

## Core Principles

### I. Single-User, No-Auth
TweakCV is a personal tool for one user. There MUST be no authentication system,
no multi-tenancy, and no user management. All code that adds auth, sessions, or
multi-user isolation is out of scope and MUST NOT be introduced.

### II. Harness-First Prompts
Model names and timeouts MUST live in `harness.json`. Prompts are stored and versioned
in **Langfuse Prompt Management** (free Hobby tier) as the primary source; `harness.json`
holds the same prompt text in the `system_prompt` field as a **fallback** for offline or
Langfuse-unavailable scenarios.

- **Primary — Langfuse:** fetch via `langfuse.get_prompt(id)` (SDK caches locally with
  TTL). Langfuse auto-versions every save and links each version to traces — no manual
  `"version"` bump or restart needed.
- **Fallback — harness.json:** if `langfuse.get_prompt()` raises, the node falls back to
  the `system_prompt` field in the matching harness entry. Bump `"version"` when the text
  changes so Langfuse traces are still tagged correctly.

### III. Human-in-the-Loop Approval
Every tailored resume MUST be reviewed by the user via Slack (Approve / Edit / Reject)
before any file is written or record saved. Nothing is persisted on Reject or expiry.
The LangGraph graph MUST pause at `await_feedback_node` using `interrupt()` and only
resume when a valid Slack interaction payload is received.

### IV. Quality Gates Before Delivery
Every resume MUST pass heuristic scoring (`score_node`) before the Slack notification
is sent:
- `keyword_coverage` MUST be ≥ 0.5; if below, the resume is silently regenerated
  once before proceeding.
- `no_hallucination` MUST pass (no new companies, dates, or skills beyond
  `base_resume.json`).
- `edit_fidelity` MUST be checked after every edit-loop iteration.
- LLM-as-judge (`quality-judge` harness) fires ONLY when heuristics score 0.4–0.6.
- All scores MUST be logged to Langfuse as trace annotations on every run.

### V. No Hallucination — Non-Negotiable
AI nodes MUST NOT invent experience, dates, companies, or skills not present in
`base_resume.json`. The `no_hallucination` heuristic check enforces this
programmatically. Any prompt change that weakens this constraint MUST be flagged in
review.

### VI. Local Storage Only
All output (PDF, SQLite database) MUST be saved locally. No cloud storage, no remote
file uploads, no external persistence beyond Langfuse observability traces.
PDF filename format: `RozaRusskikh_{Role}_2026.pdf`.

### VII. Observability by Default
Every run MUST produce a Langfuse trace. Scores (`keyword_coverage`,
`no_hallucination`, `edit_fidelity`, `quality_judge`) and the user's approval signal
MUST be attached to the trace. This dataset of labelled examples is the foundation
for future prompt improvement.

## Technology Constraints

| Layer        | Choice                          | Notes                                        |
|--------------|---------------------------------|----------------------------------------------|
| Language     | Python 3.13                     |                                              |
| Workflow     | LangGraph (SqliteSaver)         | HITL via `interrupt()`                       |
| AI           | Gemini 2.0 Flash / 2.5 Flash    | Google AI Studio free tier                   |
| Slack        | Slack Bolt for Python           | Buttons + thread replies                     |
| Webhook      | FastAPI                         | Receives Slack interaction payloads          |
| Storage      | SQLite + SQLAlchemy             | Zero-config, local                           |
| PDF          | WeasyPrint                      | HTML/CSS → PDF, no browser needed            |
| Observability| Langfuse Hobby (free)           | Tracing, evals, scores, prompt management & versioning |
| Config       | python-dotenv                   | `.env` for all secrets                       |
| Deployment   | Docker + Docker Compose         | Isolates WeasyPrint system dependencies      |


## Operational Rules

- **Slack TTL**: Pending Slack interactions expire after 24 hours. The bot MUST update
  the message to ⏰ *Expired – no action taken* and mark the job `expired` in SQLite.
- **Startup sweep**: On `main.py` startup, `stale_sweep()` MUST run once to close any
  jobs stuck in `pending` for more than 24 hours.
- **Retry policy**:
  - Layer 1 — Gemini SDK: automatic, up to 4× with exponential backoff (1 s–60 s).
  - Layer 2 — LangGraph node: up to 2 additional retries on transient errors only.
  - On hard failure: post Slack warning ⚠️, mark job `failed`, log error to Langfuse.
  - Never retry JSON parse errors or schema validation failures.
- **Edit loop cap**: Maximum 3 edit iterations per job. The graph MUST warn at 3 and
  hard-stop at 4 to prevent infinite loops.
- **Silent keyword retry**: If `keyword_coverage < 0.5`, the resume is regenerated
  once silently. The user MUST NOT see this retry.

## Governance

- This constitution supersedes all other development practices for TweakCV.
- Amendments MUST be documented with a version bump, rationale, and migration note.
- Version scheme:
  - MAJOR: backward-incompatible principle removal or redefinition.
  - MINOR: new principle or section added.
  - PATCH: clarifications, wording, typo fixes.
- All implementation plans MUST include a **Constitution Check** gate before Phase 0
  research and re-check after Phase 1 design.

**Version**: 1.0.1 | **Ratified**: 2026-05-28 | **Last Amended**: 2026-05-28
