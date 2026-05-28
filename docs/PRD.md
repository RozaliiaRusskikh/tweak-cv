# TweakCV – Product Requirements Document

## Problem

Tailoring a resume for each job application is slow and repetitive. Manually matching keywords, rewriting bullets, and adjusting the summary takes 30–60 minutes per application.

## Solution

Paste a job description → AI compares it to your base resume → generates a tailored version → you review and approve in Slack → PDF saved locally.

## Users

Single user (personal tool). No auth, no multi-tenancy.

## Core Flow

1. User pastes a job description (CLI)
2. Agent extracts key skills, role requirements, keywords, company name, and role title
3. Agent generates a tailored resume → reorders bullets, adjusts summary, matches terminology
4. Slack message sent with three buttons: **Approve | Edit | Reject**
5. **Approve** → export PDF, save to disk, record stored in SQLite → done
6. **Edit** → bot asks "What would you like to change?" → user replies in thread → agent applies edits → loop back to step 4
7. **Reject** → discard, nothing saved

## Timeout / No-Response Behaviour

If the user does not respond to a Slack message:

- **Slack buttons expire after 24 hours** → the bot updates the message to show ⏰ *Expired – no action taken* and disables the buttons
- **LangGraph thread marked `expired`** → on `main.py` startup, a one-shot sweep checks for jobs stuck in `pending` for more than 24 hours and closes them cleanly
- **Nothing is saved** → expired threads are treated the same as Reject

If the user starts an **Edit loop** but stops replying mid-thread:
- Same 24-hour TTL from the timestamp of the last bot message
- After expiry bot posts: ⏰ *No reply received – resumé discarded*
- Thread marked `expired`

## Retry Behaviour

If the AI call fails (network error, rate limit, timeout):
- Gemini SDK retries automatically up to 4× with exponential backoff (built-in)
- If all retries fail, LangGraph retries the whole node up to 2 more times
- If the node still fails after all retries, the bot sends a Slack message: ⚠️ *Something went wrong – please resubmit the job description*
- Job marked `failed` in SQLite; nothing saved

## Quality Evals

Every tailored resume is automatically scored before it is sent to Slack:

| Score | Type | What it checks |
|-------|------|----------------|
| `keyword_coverage` | Heuristic (0–1) | % of JD required keywords present in tailored resume |
| `no_hallucination` | Heuristic (pass/fail) | No new company names, dates, or skills invented beyond base resume |
| `edit_fidelity` | Heuristic (0–1) | Edit loop only – did the edit apply the requested change? |
| `quality` | LLM-as-judge (0–1) | Only fires when heuristics are borderline (0.4–0.6) |

Scores are logged to **Langfuse** (free Hobby tier) as trace annotations on every run. User's Approve / Reject is also logged as a ground-truth signal. This creates a dataset of labelled examples over time.

If `keyword_coverage < 0.5`, the resume is automatically regenerated once before being sent to Slack (silent retry – user never sees it).

## Constraints

- Base resume stored as structured JSON (`summary`, `experience`, `skills`, `education`)
- PDF filename: `RozaRusskikh_{Role}_2026.pdf`
- No cloud storage – all files saved locally
- AI provider: Gemini 2.5 Flash (Google AI Studio free tier)
- Observability: Langfuse Hobby tier (free, 50k observations/month)

## Out of Scope (v1)

- Multi-resume support
- Cover letter generation
- Job application tracking
- Web UI
- Push reminders before expiry
- Automated prompt improvement from eval data (v2)
