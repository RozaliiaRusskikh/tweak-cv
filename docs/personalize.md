# Personalizing TweakCV for Your Own Job Search

Everything specific to *one person's* job search lives in a handful of files and
environment variables. Replace these and the rest of the pipeline (LangGraph
workflow, scoring, Slack review, PDF export) works unchanged.

## 1. Your resume — `tweakcv/base_resume.json`

This is the single source of truth for tailoring **and** for hallucination
detection — `score_node._detect_new_entities()` flags anything in a tailored
resume that can't be traced back to this file, so keep it accurate and
complete.

Required shape (must match `TailoredResumeOutput` in `schemas.py`):

```json
{
  "name": "Your Name",
  "email": "you@example.com",
  "linkedin": "linkedin.com/in/you",
  "github": "github.com/you",
  "summary": "...",
  "experience": [
    {
      "company": "...",
      "role": "...",
      "dates": "Mon YYYY – Mon YYYY",
      "bullets": ["...", "..."]
    }
  ],
  "skills": ["...", "..."],
  "education": [
    { "institution": "...", "degree": "...", "year": "..." }
  ]
}
```

> **Note for Claude Code users**: this file is write-protected by
> `.claude/hooks/protect-files.sh` (listed under `WRITE_ONLY`). The agent can
> read it but won't edit it — update it yourself.

## 2. Your context — `tweakcv/personal.json` (optional)

Adds voice, values, and background that go beyond what's on the resume —
`tailor_node` and `edit_node` use it to shape the summary's tone. If the file
doesn't exist, `runner.py` falls back to `{}` and tailoring proceeds without it.

```json
{
  "name": "Your Name",
  "values": ["...", "..."],
  "mission": "What kind of roles/companies you're targeting and why.",
  "background_story": "Your career narrative in your own words.",
  "lived_in": ["..."],
  "cultural_note": "...",
  "personal_facts": ["..."],
  "strengths_beyond_resume": ["..."],
  "tone": {
    "warm": true,
    "direct": true,
    "formal": false,
    "avoid": ["corporate buzzwords", "..."]
  }
}
```

## 3. Environment — `.env`

```bash
cp .env.example .env
```

All of these are **required** — the app fails to start without them
(`Settings` in `settings.py` has no defaults for them):

| Variable | Where it comes from |
|---|---|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) — free tier |
| `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_CHANNEL_ID` | Your own Slack app — see [slack-setup.md](slack-setup.md) |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Your own [Langfuse](https://cloud.langfuse.com) project — free Hobby tier |

Optional:

| Variable | Default | Notes |
|---|---|---|
| `GEMINI_API_KEY_EVAL` | falls back to `GEMINI_API_KEY` | second key so eval runs don't burn production quota |
| `PUBLIC_URL` | `""` | your ngrok static domain — see [ngrok-setup.md](ngrok-setup.md) |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | only change if self-hosting |
| `OUTPUT_DIR` | `output/resumes` | where approved PDFs are saved |
| `DATABASE_URL` | `sqlite:////app/data/tailorcv.db` | leave as-is for Docker |

Full step-by-step for getting each value: [env-setup.md](env-setup.md).

## 4. Your Slack workspace & channel

1. Create your own Slack app and install it to **your** workspace — [slack-setup.md](slack-setup.md).
2. Pick (or create) the channel where tailored resumes should be posted, and copy its Channel ID into `SLACK_CHANNEL_ID`.
3. Point the app's **Interactivity** and **Event Subscriptions** request URLs at your own `PUBLIC_URL` (ngrok) — see [ngrok-setup.md](ngrok-setup.md).

## 5. Optional: PDF look & feel — `tweakcv/templates/resume.html`

Plain Jinja2 + CSS, rendered to PDF via WeasyPrint. Edit fonts, spacing, and
layout here to match your preferred resume style.

## 6. Optional: prompts — `tweakcv/harness.json`

Local fallback prompts for `analyze-jd`, `tailor-resume`, `edit-resume`, and
`quality-judge`. Edit the wording/instructions, then push to your own Langfuse
project:

```bash
uv run python -m tweakcv.seed_prompts
```

## Checklist

- [ ] `tweakcv/base_resume.json` replaced with your resume
- [ ] `tweakcv/personal.json` replaced (or removed) with your context
- [ ] `.env` filled in — Gemini, Slack, Langfuse keys
- [ ] Your own Slack app created, installed, channel ID set
- [ ] ngrok static domain configured and pasted into Slack app URLs
- [ ] (optional) `resume.html` styled to your taste
- [ ] (optional) `harness.json` prompts seeded to your Langfuse project
- [ ] `docker compose up --build`
