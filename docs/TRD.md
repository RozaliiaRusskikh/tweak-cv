# TweakCV – Technical Requirements Document

## Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Language | Python 3.13 |
| Workflow | LangGraph | Built-in HITL, interrupt/resume, SqliteSaver checkpointer |
| AI | Gemini 2.0 Flash (Google AI Studio) | Free tier – 1,500 req/day, no credit card |
| Slack | Slack Bolt for Python | Button interactions + thread replies |
| Webhook | FastAPI | Receives Slack interaction payloads |
| Storage | SQLite + SQLAlchemy | Zero-config, local, no running server |
| PDF | WeasyPrint | HTML/CSS → PDF, pure Python, no browser needed |
| Observability | Langfuse Hobby (free) | Tracing, evals, scores, prompt management & versioning |
| Config | python-dotenv | `.env` for API keys |
| Deployment | Docker + Docker Compose | Native isolation of Weasyprint's underlying system graphical/font libraries. |

---

## Harness File (`harness.json`)

Prompts and model config live outside code – versioned independently, swappable without touching Python.

```json
{
  "harnesses": [
    {
      "id": "analyze-jd",
      "name": "JD Analyzer",
      "system_prompt": "Extract structured data from a job description. Return: company (string), role (string), required_skills (list), preferred_skills (list), keywords (list). Return JSON only.",
      "model_name": "gemini-2.0-flash",
      "result_type_name": "JDAnalysisOutput",
      "timeout_seconds": 30.0
    },
    {
      "id": "tailor-resume",
      "name": "Resume Tailor",
      "system_prompt": "You are a resume tailoring agent. Given a base resume (JSON) and a job description analysis, produce a tailored resume that: reorders bullets to match required_skills, adjusts the summary to mirror the role's language, inserts keywords naturally. Never invent experience, dates, or companies not in the base resume. Return JSON matching TailoredResumeOutput.",
      "model_name": "gemini-2.0-flash",
      "result_type_name": "TailoredResumeOutput",
      "timeout_seconds": 60.0
    },
    {
      "id": "edit-resume",
      "name": "Resume Editor",
      "system_prompt": "You are a resume editing agent. Apply the user's requested change to the tailored resume. Only modify what the user asked for – do not rewrite other sections. Return JSON matching TailoredResumeOutput.",
      "model_name": "gemini-2.5-flash",
      "result_type_name": "TailoredResumeOutput",
      "timeout_seconds": 60.0
    },
    {
      "id": "quality-judge",
      "name": "Quality Judge",
      "system_prompt": "You are a resume quality evaluator. Given a tailored resume and the job description it was tailored for, score the resume quality from 0.0 to 1.0. Consider: keyword alignment, relevance of bullet points, natural language flow, no hallucinated facts. Return JSON: {score: float, reasoning: string}.",
      "model_name": "gemini-2.5-flash",
      "result_type_name": "QualityJudgeOutput",
      "timeout_seconds": 30.0
    }
  ]
}
```

> **Rule:** Model names and timeouts always live in `harness.json`. Prompts are stored
> and versioned in **Langfuse Prompt Management** (free Hobby tier) as the primary source;
> `harness.json` holds the same prompt text as a **fallback** for offline or Langfuse-
> unavailable scenarios.
>
> - **Primary – Langfuse:** fetch at runtime via `langfuse.get_prompt(id)`. The SDK caches
>   locally (TTL-based), so no per-call latency. Langfuse auto-versions every save and links
>   each version to traces — no manual `"version"` bump or restart needed.
> - **Fallback – harness.json:** if `langfuse.get_prompt()` raises (network error, service
>   down), the node falls back to the `system_prompt` field in the matching harness entry.
>   Bump `"version"` when the text changes (e.g. `"version": "v3"`) so traces are still tagged.

---

## Architecture

```
main.py startup
  └── stale_sweep()       one-shot: expire pending jobs > 24h old, update Slack

CLI
 ↓ job description text
 ↓
LangGraph StateGraph  (SqliteSaver checkpointer)
 │
 ├── analyze_node          harness: analyze-jd
 │                         → extracts company, role, keywords
 │
 ├── tailor_node           harness: tailor-resume
 │                         → generates tailored resume
 │                         → score_node runs inline (heuristics + optional judge)
 │                         → if keyword_coverage < 0.5: silent retry once, then continue
 │
 ├── notify_node           post Slack (Approve / Edit / Reject)
 │                         → update jobs.last_activity_at
 │
 ├── await_feedback_node   interrupt() → graph pauses
 │       ├── approve  → finalize_node
 │       ├── edit     → edit_node → tailor_node  (loop, max 3 iterations)
 │       ├── reject   → END  (nothing saved)
 │       └── expired  → END  (nothing saved)
 │
 ├── edit_node             harness: edit-resume
 │                         → applies user feedback
 │                         → score_node runs inline (edit_fidelity check)
 │
 ├── score_node            heuristic scorer (always runs, no LLM)
 │       ├── keyword_coverage  ≥ 0.5 → pass
 │       ├── no_hallucination  → pass/fail
 │       ├── edit_fidelity     → pass/fail (edit loop only)
 │       └── quality (LLM-as-judge, harness: quality-judge)
 │               only fires when heuristics score 0.4–0.6 (borderline)
 │               → all scores logged to Langfuse as trace annotations
 │
 ├── error_node            on node failure after all retries
 │       → posts Slack: ⚠️ Something went wrong – please resubmit
 │       → marks job status='failed'
 │       → logs error trace to Langfuse
 │
 └── finalize_node         export PDF + save to SQLite
```

---

## Retry Logic

Two layers – SDK and graph:

```
Layer 1 – Gemini SDK (automatic, free):
  transient errors (429, 408, 5xx) → retry up to 4× with exp backoff (1s–60s)
  built into google-genai SDK, no config needed

Layer 2 – LangGraph node retry (explicit):
  if SDK exhausts retries and raises → LangGraph catches in error_node
  error_count in state: 0 → retry node once → retry again → hard fail
  max_node_retries = 2  (configurable in harness.json)
  on hard fail: post Slack warning, mark job='failed', log to Langfuse

Retry only on: network errors, timeouts, rate limits (transient)
Never retry on: JSON parse errors, schema validation failures (permanent – fix the prompt)
```

---

## Edit Loop Cap

Tracked via `iteration` in `TailorState` (incremented inside `edit_node`):

```
iteration = 0  (initial)

on each edit route:
  iteration += 1

  if iteration == 3:
    → notify_node appends warning to Slack message:
      ⚠️ This is your last edit – approve or reject after this

  if iteration >= 4:
    → await_feedback_node hard-stops before routing to edit_node
    → bot posts: ⚠️ Maximum edits reached – please approve or reject the current version
    → Edit button removed from Slack message
    → job stays 'pending' until Approve / Reject / 24h expiry
```

Guard lives in `await_feedback_node`, checked before routing to `edit_node`. No change to
retry logic or scoring — the cap is orthogonal to those.

---

## Eval / Scoring Design

```python
# score_node.py  – runs after tailor_node and edit_node

def score_resume(tailored: dict, jd_analysis: dict, feedback: str | None,
                 langfuse_trace) -> ScoreResult:

    # --- Heuristic 1: keyword coverage (deterministic, free) ---
    jd_keywords  = set(k.lower() for k in jd_analysis["keywords"])
    resume_text  = json.dumps(tailored).lower()
    covered      = sum(1 for k in jd_keywords if k in resume_text)
    kw_score     = covered / len(jd_keywords) if jd_keywords else 1.0

    # --- Heuristic 2: hallucination check (deterministic, free) ---
    base_text    = json.dumps(BASE_RESUME).lower()
    hallucinated = _detect_new_entities(tailored, base_text)  # new names/dates/companies
    no_halluc    = len(hallucinated) == 0

    # --- Heuristic 3: edit fidelity (only in edit loop) ---
    edit_fid = _check_edit_applied(feedback, tailored) if feedback else None

    # --- LLM-as-judge: only fires when kw_score is borderline ---
    quality_score = None
    if 0.4 <= kw_score <= 0.6:
        quality_score = _run_quality_judge(tailored, jd_analysis)  # harness: quality-judge

    # --- Log all scores to Langfuse ---
    langfuse_trace.score(name="keyword_coverage", value=kw_score)
    langfuse_trace.score(name="no_hallucination", value=1.0 if no_halluc else 0.0)
    if edit_fid is not None:
        langfuse_trace.score(name="edit_fidelity", value=edit_fid)
    if quality_score is not None:
        langfuse_trace.score(name="quality_judge", value=quality_score)

    return ScoreResult(
        keyword_coverage=kw_score,
        no_hallucination=no_halluc,
        edit_fidelity=edit_fid,
        quality=quality_score,
        needs_retry=kw_score < 0.5  # triggers silent regeneration in tailor_node
    )
```

**User signal as eval:**
```python
# In slack_handler.py – when user clicks Approve or Reject
langfuse.score(
    trace_id=job.langfuse_trace_id,
    name="user_approval",
    value=1.0 if action == "approve" else 0.0,
    comment=action  # "approve" | "reject"
)
```

---

## Startup Sweep (replaces APScheduler)

```python
# main.py – runs once on startup, synchronous, < 1 second
def stale_sweep(db_session, graph, slack_client):
    """Expire any pending jobs older than 24h. Runs once at startup."""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    stale  = db_session.query(Job).filter(
        Job.status == "pending",
        Job.last_activity_at < cutoff
    ).all()
    for job in stale:
        slack_client.chat_update(
            channel=SLACK_CHANNEL_ID,
            ts=job.slack_ts,
            text="⏰ Expired – no action taken (24h passed)",
            blocks=[]
        )
        config = {"configurable": {"thread_id": job.thread_id}}
        graph.invoke(Command(resume="expired"), config=config)
        job.status = "expired"
    db_session.commit()
    if stale:
        print(f"[startup] expired {len(stale)} stale job(s)")
```

> No APScheduler, no background thread. If the app is running (you just launched it),
> stale jobs get cleaned up. For a personal tool that's exactly enough.

---

## Data Model (SQLite)

```sql
jobs (
    id                INTEGER  PRIMARY KEY,
    company           TEXT     NOT NULL,
    role              TEXT     NOT NULL,
    jd_text           TEXT     NOT NULL,
    status            TEXT     NOT NULL DEFAULT 'pending',
                      -- pending | approved | rejected | expired | failed
    thread_id         TEXT     NOT NULL UNIQUE,
    slack_ts          TEXT,
    langfuse_trace_id TEXT,                     -- for linking user feedback to trace
    last_activity_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)

resume_versions (
    id               INTEGER  PRIMARY KEY,
    job_id           INTEGER  NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    version          INTEGER  NOT NULL,
    content          TEXT     NOT NULL,  -- JSON: {summary, experience, skills, education}
    keyword_coverage REAL,               -- heuristic score logged here too
    approved         BOOLEAN  NOT NULL DEFAULT FALSE,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)

CREATE INDEX IF NOT EXISTS idx_resume_versions_job_id ON resume_versions(job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status_activity   ON jobs(status, last_activity_at);
```

---

## LangGraph State

```python
from typing import Optional
from typing_extensions import TypedDict

class TailorState(TypedDict):
    job_id:             int
    thread_id:          str
    langfuse_trace_id:  str              # set at graph start; used to attach scores
    company:            str
    role:               str
    jd_text:            str
    jd_analysis:        Optional[dict]   # output of analyze_node
    base_resume:        dict
    tailored_resume:    Optional[dict]   # None until tailor_node runs
    slack_ts:           str
    iteration:          int              # edit loop counter (warn at 3, hard stop at 4)
    feedback:           str              # user's edit instructions
    status:             str              # pending | approved | rejected | expired | failed
    error_count:        int              # node retry counter (max 2)
    last_error:         Optional[str]    # last exception message, for Slack warning
    scores:             Optional[dict]   # latest ScoreResult as dict
```

---

## Environment Variables

```
GEMINI_API_KEY=          # Google AI Studio – free, no credit card
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=
SLACK_CHANNEL_ID=
LANGFUSE_PUBLIC_KEY=     # Langfuse Hobby – free, no credit card
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# Added for Database isolation in Docker volume
DATABASE_URL=sqlite:////app/data/tailorcv.db
```

---

## Project Structure

```
tweakrcv/
├── main.py               # CLI entrypoint + startup stale_sweep()
├── harness.json          # all prompts, model names, timeouts – edit here, not in Python
├── graph.py              # LangGraph state machine
├── nodes/
│   ├── analyze.py        # harness: analyze-jd
│   ├── tailor.py         # harness: tailor-resume; calls score_node inline
│   ├── notify.py         # post Slack; update last_activity_at
│   ├── edit.py           # harness: edit-resume; calls score_node inline
│   ├── score.py          # heuristics + LLM-as-judge + Langfuse logging
│   ├── error.py          # Slack warning + mark job failed
│   └── finalize.py       # export PDF + save to SQLite
├── slack_handler.py      # FastAPI + Slack Bolt webhook; logs user_approval to Langfuse
├── db.py                 # SQLAlchemy models + session
├── evals/
│   ├── dataset.json      # labelled examples: {jd, base_resume, expected_keywords}
│   └── run_evals.py      # offline eval runner – compare prompt versions via Langfuse
├── base_resume.json      # your base resume (source of truth)
├── templates/
│   └── resume.html       # WeasyPrint HTML template
└── .env
```
