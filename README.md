# TweakCV

Paste a job description → AI tailors your resume → review in Slack → PDF saved locally.

## How it works

![TweakCV Full Architecture](docs/architecture.png)

**Score gates** run on every version before Slack is notified:
- `keyword_coverage` — % of JD keywords present (retry if < 0.5)
- `no_hallucination` — no invented companies, dates, or skills
- `edit_fidelity` — did the edit apply what was asked? (edit loop only)
- `quality` — LLM judge, fires only when heuristics are borderline (0.4–0.6)

All scores + user Approve/Reject are logged to Langfuse.

## Stack

| | |
|---|---|
| Workflow | LangGraph (HITL, SqliteSaver checkpointer) |
| AI | Gemini 2.0/2.5 Flash (Google AI Studio free tier) |
| Notifications | Slack Bolt + FastAPI webhook |
| PDF | WeasyPrint |
| Storage | SQLite + SQLAlchemy |
| Observability | Langfuse Hobby (free) |
| Runtime | Docker + Docker Compose |

## Setup

```bash
cp .env.example .env   # then fill in your keys
docker compose up
```

## Usage

```bash
python main.py "$(pbpaste)"   # paste JD from clipboard
```

PDFs are saved as `RozaRusskikh_{Role}_2026.pdf`.

## Docs

- [PRD](docs/PRD.md) — product requirements
- [TRD](docs/TRD.md) — technical requirements & architecture
