# Environment Setup

Copy `.env.example` to `.env` before running anything:

```bash
cp .env.example .env
```

---

## GEMINI_API_KEY

**What it is**: API key for Gemini 2.0/2.5 Flash — the LLM used for all resume tailoring.

**How to get it**:
1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Sign in with a Google account (no credit card required for free tier)
3. Click **Create API key**
4. Copy the key — it starts with `AIza...`

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
