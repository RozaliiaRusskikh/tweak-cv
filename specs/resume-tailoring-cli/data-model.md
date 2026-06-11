# Data Model: Resume Tailoring CLI

**Feature**: `resume-tailoring-cli` | **Date**: 2026-06-01

## SQLite Schema (`tailorcv.db`)

### `jobs` table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PK | Auto-increment |
| `company` | TEXT | NOT NULL | Extracted by `analyze_node` |
| `role` | TEXT | NOT NULL | Extracted by `analyze_node` |
| `jd_text` | TEXT | NOT NULL | Raw CLI input |
| `status` | TEXT | NOT NULL, DEFAULT `'pending'` | Enum: `pending`, `approved`, `rejected`, `expired`, `failed` |
| `thread_id` | TEXT | NOT NULL, UNIQUE | uuid4; LangGraph checkpoint key |
| `slack_ts` | TEXT | nullable | Slack message timestamp (for `chat_update` and thread replies) |
| `langfuse_trace_id` | TEXT | nullable | Links Slack button actions back to the Langfuse trace |
| `last_activity_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Updated by `notify_node` and `stale_sweep` |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Set once at job creation |

**Status transitions**:
```
pending → approved    (user clicks Approve → finalize_node runs)
pending → rejected    (user clicks Reject)
pending → expired     (stale_sweep: last_activity_at > 24h ago)
pending → failed      (error_node: all node retries exhausted)
```

### `resume_versions` table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PK | Auto-increment |
| `job_id` | INTEGER | NOT NULL, FK→`jobs(id)` ON DELETE CASCADE | Parent job |
| `version` | INTEGER | NOT NULL | Matches `TailorState.iteration` at save time |
| `content` | TEXT | NOT NULL | JSON: `{summary, experience, skills, education}` |
| `keyword_coverage` | REAL | nullable | `score_node` heuristic value at this version |
| `approved` | BOOLEAN | NOT NULL, DEFAULT FALSE | TRUE only for the final approved version |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | |

### Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_resume_versions_job_id
    ON resume_versions(job_id);

CREATE INDEX IF NOT EXISTS idx_jobs_status_activity
    ON jobs(status, last_activity_at);
```

---

## LangGraph State: `TailorState`

Defined as a `TypedDict` in `graph.py`. LangGraph merges partial dicts returned by nodes.

```python
class TailorState(TypedDict):
    job_id:             int
    thread_id:          str             # uuid4; SqliteSaver checkpoint key
    langfuse_trace_id:  str             # set once in main.py before graph starts
    company:            str             # set by analyze_node
    role:               str             # set by analyze_node
    jd_text:            str             # raw CLI input
    jd_analysis:        Optional[dict]  # JDAnalysisOutput.model_dump()
    base_resume:        dict            # loaded from base_resume.json at startup
    tailored_resume:    Optional[dict]  # TailoredResumeOutput.model_dump()
    slack_ts:           str             # set by notify_node (Slack message timestamp)
    iteration:          int             # 0 initial; ++ in edit_node; warn@3, hard stop@4
    feedback:           str             # "approve"|"reject"|"edit:<text>"|"expired"
    status:             str             # mirrors jobs.status
    error_count:        int             # node retry counter; max 2 before hard fail
    last_error:         Optional[str]   # exception message for Slack/Langfuse error
    scores:             Optional[dict]  # ScoreResult.model_dump()
```

**State update rules**:
- Each node returns a partial dict; LangGraph merges it into state
- `feedback` is set by `slack_handler` via `Command(resume=feedback)` before `await_feedback_node` routes
- `iteration` only incremented in `edit_node` (not in `tailor_node`)
- `scores` is overwritten on each `score_node` call (latest scores only; history is in `resume_versions`)

---

## Pydantic Schemas (`schemas.py`)

Used with `langchain-google-genai`'s `.with_structured_output()` for all LLM calls.

```python
class ExperienceEntry(BaseModel):
    company: str
    role: str
    dates: str
    bullets: list[str]

class EducationEntry(BaseModel):
    institution: str
    degree: str
    year: str

class JDAnalysisOutput(BaseModel):
    """Output of analyze_node (harness: analyze-jd)"""
    company: str
    role: str
    required_skills: list[str]
    preferred_skills: list[str]
    keywords: list[str]

class TailoredResumeOutput(BaseModel):
    """Output of tailor_node and edit_node"""
    summary: str
    experience: list[ExperienceEntry]
    skills: list[str]
    education: list[EducationEntry]

class QualityJudgeOutput(BaseModel):
    """Output of quality-judge harness (fires only when kw_coverage in 0.4–0.6)"""
    score: float     # 0.0 – 1.0
    reasoning: str

class ScoreResult(BaseModel):
    """Internal scoring result; stored as dict in TailorState.scores"""
    keyword_coverage: float
    no_hallucination: bool
    edit_fidelity: float | None    # None when not in edit loop
    quality: float | None          # None when kw_coverage not in 0.4–0.6
    needs_retry: bool              # True when keyword_coverage < 0.5
```

---

## `base_resume.json` Structure

Source of truth for hallucination detection. Shape must match `TailoredResumeOutput`:

```json
{
  "name": "Roza Russkikh",
  "summary": "...",
  "experience": [
    {
      "company": "...",
      "role": "...",
      "dates": "...",
      "bullets": ["..."]
    }
  ],
  "skills": ["..."],
  "education": [
    {
      "institution": "...",
      "degree": "...",
      "year": "..."
    }
  ]
}
```

`score_node._detect_new_entities()` compares all company names, dates, and named entities in the tailored resume against the full JSON text of `base_resume.json`. Any entity found in the tailored resume but absent from the base resume is flagged as a potential hallucination.
