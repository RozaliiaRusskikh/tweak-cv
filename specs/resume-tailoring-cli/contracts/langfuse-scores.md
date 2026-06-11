# Langfuse Trace Contract

**Files**: `tweakcv/nodes/score.py`, `tweakcv/nodes/finalize.py`, `tweakcv/slack_handler.py`

## Trace Lifecycle

One Langfuse trace is created per job in `runner.py::run_job()` (called from `slack_handler.py` when a JD is submitted via Slack):

```python
langfuse = get_langfuse()
trace_id = langfuse.create_trace_id()
langfuse.start_observation(
    trace_context={"trace_id": trace_id},
    name="resume-tailoring",
    input={"jd_text": jd_text[:500]},
).end()
```

`trace_id` is stored in `TailorState["langfuse_trace_id"]` and `jobs.langfuse_trace_id` (DB). All nodes reference it by ID via `trace_context={"trace_id": ...}` — they do not hold a reference to the trace/span object.

### Tailored resume output

`nodes/score.py::_attach_trace_output()` runs after every `tailor_node`/`edit_node` call and creates a `tailored-resume` observation on the trace with `output=<tailored resume dict>`, via the standard (non-deprecated) `output=` parameter on `start_observation()`. Each call adds a new observation reflecting that iteration's resume.

To use this for LLM-as-a-judge "Quality Judge" scoring in Langfuse, configure the evaluator's target scope as **Observation** with `name == "tailored-resume"`.

## Scores

| Score name | Type | Attached by | Trigger | Value range |
|------------|------|------------|---------|-------------|
| `keyword_coverage` | float | `nodes/score.py` | After `tailor_node` and `edit_node` | 0.0 – 1.0 |
| `no_hallucination` | float | `nodes/score.py` | After `tailor_node` and `edit_node` | 0.0 (fail) or 1.0 (pass) |
| `edit_fidelity` | float | `nodes/score.py` | `edit_node` only | 0.0 – 1.0 |
| `user_approval` | float | `nodes/finalize.py` (approve) or `slack_handler.py` (reject) | On user Approve or Reject | 0.0 or 1.0 |

### Score attachment pattern

```python
langfuse_client.trace(id=state["langfuse_trace_id"]).score(
    name="keyword_coverage",
    value=kw_score,
    comment="heuristic: covered/total keywords"
)
```

## Prompt Management

Langfuse Prompt IDs must match `harness.json` `id` fields exactly:

| Prompt ID | Harness | Model | Used in |
|-----------|---------|-------|---------|
| `analyze-jd` | JD Analyzer | `gemini-2.0-flash` | `nodes/analyze.py` |
| `tailor-resume` | Resume Tailor | `gemini-2.0-flash` | `nodes/tailor.py` |
| `edit-resume` | Resume Editor | `gemini-2.5-flash` | `nodes/edit.py` |

Prompts are fetched at runtime via `harness_loader.get_prompt(id)`. The Langfuse SDK caches locally with TTL — no per-call network overhead after warmup. Fallback: `harness.json["system_prompt"]` used if `langfuse_client.get_prompt()` raises any exception.

## Offline Evals (`evals/run_evals.py`)

Uploads scored examples as Langfuse dataset runs. Each run links to:
- The prompt version used
- The `JDAnalysisOutput` and `TailoredResumeOutput` produced
- Heuristic scores (`keyword_coverage`, `no_hallucination`)

This enables comparing prompt versions A vs B across the same labelled dataset without touching the production graph.
