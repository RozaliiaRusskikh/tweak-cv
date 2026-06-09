# Environment Setup

Copy `.env.example` to `.env` before running anything:

```bash
cp .env.example .env
```

---

## GEMINI_API_KEY

**What it is**: API key for Gemini 2.5 Flash Lite — the LLM used for all resume tailoring (analyze, tailor, edit).

**How to get it**:
1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Sign in with a Google account (no credit card required for free tier)
3. Click **Create API key**
4. Copy the key — it starts with `AIza...`

---

## GEMINI_API_KEY_EVAL

**What it is**: Optional separate API key used only by the eval runner (`evals/run_evals.py --regen`). Keeps eval runs from consuming your production quota.

**How to get it**: Create a second key at the same link above. Both keys get their own free-tier quota (20 requests/day).

If not set, the eval runner falls back to `GEMINI_API_KEY`.

---

## PUBLIC_URL

**What it is**: Your ngrok static domain — used as the webhook base URL in Slack app settings.

**How to get it**:
1. Follow [ngrok-setup.md](ngrok-setup.md) to claim your free static domain
2. Set it as: `PUBLIC_URL=https://<your-static-domain>`

Paste `$PUBLIC_URL/slack/events` into both Interactivity and Event Subscriptions in your Slack app.

---

## Slack

Three values are needed. All come from the same Slack app.

**How to create the app**:
1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name it (e.g. `TweakCV`) and select your workspace

### SLACK_BOT_TOKEN

1. In your app settings → **OAuth & Permissions**
2. Under **Bot Token Scopes**, add: `chat:write`, `chat:write.public`, `channels:history`
3. Click **Install to Workspace** → **Allow**
4. Copy **Bot User OAuth Token** — starts with `xoxb-...`

### SLACK_SIGNING_SECRET

1. In your app settings → **Basic Information**
2. Under **App Credentials**, copy **Signing Secret**

### SLACK_CHANNEL_ID

1. In Slack, right-click the channel you want the bot to post to
2. Select **View channel details** → scroll to the bottom
3. Copy the **Channel ID** — starts with `C...`

**Required before running**: enable these in your app settings:
- **Interactivity & Shortcuts** → Request URL: `https://<your-ngrok-domain>/slack/events`
- **Event Subscriptions** → Request URL: same → subscribe to `message.channels`

For local dev, run `ngrok http 3000` first to get the public URL.

---

## Langfuse

**What it is**: Observability and prompt management. Traces every run, stores scores, manages prompt versions.

**How to get it**:
1. Go to [cloud.langfuse.com](https://cloud.langfuse.com) and sign up (free Hobby tier, no credit card)
2. Create a new project (e.g. `tweak-cv`)
3. Go to **Settings** → **API Keys** → **Create new API key**
4. Copy both **Public Key** (`pk-lf-...`) and **Secret Key** (`sk-lf-...`)

### LANGFUSE_HOST

Leave as `https://cloud.langfuse.com` (the default Langfuse Cloud). Only change this if you self-host Langfuse.

### Prompt sync

Prompts are defined in `tweakcv/harness.json` and mirrored to Langfuse.

### LLM-as-a-Judge Evaluator (set up after first run)

Quality scoring is done entirely by Langfuse — there is no inline LLM judge in the app code. After your first successful run, configure a native Langfuse evaluator so every future trace is auto-scored:

1. Seed the `quality-judge` prompt to Langfuse first (if you haven't already):
   ```bash
   uv run python -m tweakcv.seed_prompts
   ```
2. Go to **Evaluation** → **Evaluators** → **Create evaluator**
3. Set **Name**: `quality-judge`
4. Set **Type**: `LLM-as-a-judge`
5. Under **Model**, choose any provider/model available in your Langfuse account (e.g. `gpt-4o-mini` or `gemini-1.5-flash`)
6. Under **Prompt template**, select the `quality-judge` prompt from the dropdown (seeded in step 1)
7. Map variables:
   - `{{input}}` → trace **input** (the job description)
   - `{{output}}` → trace **output** (the tailored resume)
8. Set **Score name**: `quality_judge`
9. Set **Trace filter**: `name = resume-tailoring`
10. Click **Save** — Langfuse will auto-run this evaluator on every new matching trace

You can also trigger it manually on any existing trace: open the trace → **Scores** tab → **Run evaluator**.

**Push local → Langfuse** (run after editing `harness.json`):
```bash
uv run python -m tweakcv.seed_prompts
```

**Pull Langfuse → local** (run after editing a prompt in the Langfuse UI):
```bash
uv run python -m tweakcv.pull_prompts
```

### Eval dataset sync

Eval examples are defined in `evals/dataset.json` and mirrored to Langfuse Datasets for UI visibility.

**Push local → Langfuse** (run after editing `evals/dataset.json`):
```bash
uv run python -m tweakcv.seed_evals
```

**Pull Langfuse → local** (run after adding/editing examples in the Langfuse UI):
```bash
uv run python -m tweakcv.pull_evals
```

Or sync everything at once:
```bash
uv run python evals/sync_langfuse.py
```

---

## DATABASE_URL

Leave as-is:

```
DATABASE_URL=sqlite:////app/data/tailorcv.db
```

This path is inside the Docker volume. If running outside Docker (e.g. for local dev without Docker), change to a local path:

```
DATABASE_URL=sqlite:///./data/tailorcv.db
```
