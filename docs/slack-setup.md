# Slack App Setup

Step-by-step guide to configure a Slack app for tweak-cv.

---

## 1. Create the App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Enter a name (e.g. `TweakCV`) and select your workspace
4. Click **Create App**

---

## 2. Bot Token Scopes

In the left sidebar: **OAuth & Permissions** → scroll to **Scopes** → **Bot Token Scopes**

Add these scopes:

| Scope | Purpose |
|---|---|
| `chat:write` | Post resume review messages to a channel |
| `chat:write.public` | Post to channels the bot hasn't joined |
| `channels:history` | Read thread replies (edit text capture) |

Click **Save Changes** after adding scopes.

---

## 3. Install the App to Your Workspace

In **OAuth & Permissions** → click **Install to Workspace** → **Allow**.

Copy the credentials you'll need:

| Value | Where to find it | Env variable |
|---|---|---|
| Bot User OAuth Token | OAuth & Permissions → OAuth Tokens | `SLACK_BOT_TOKEN` |
| Signing Secret | Basic Information → App Credentials | `SLACK_SIGNING_SECRET` |

> If you add scopes after installing, you must reinstall the app for the new scopes to take effect. A yellow banner will appear at the top of OAuth & Permissions reminding you.

---

## 4. Get the Channel ID

1. In Slack, open the channel where the bot should post resume reviews
2. Right-click the channel name → **View channel details**
3. Scroll to the bottom — copy the **Channel ID** (starts with `C...`)
4. Add it to `.env` as `SLACK_CHANNEL_ID`

---

## 5. Interactivity (required for Approve / Edit / Reject buttons)

Before you start, make sure ngrok is running and pointing to port 3000:

```bash
ngrok http 3000
```

Copy the `https://` URL (e.g. `https://abc123.ngrok-free.app`).

In the left sidebar: **Interactivity & Shortcuts**

1. Toggle **Interactivity** → **ON**
2. In **Request URL**, enter:
   ```
   https://<your-ngrok-url>/slack/events
   ```
3. Click **Save Changes**

---

## 6. Event Subscriptions (required for Edit thread replies)

In the left sidebar: **Event Subscriptions**

1. Toggle **Enable Events** → **ON**
2. In **Request URL**, enter:
   ```
   https://<your-ngrok-url>/slack/events
   ```
   Wait for the **Verified ✓** checkmark to appear.
3. Under **Subscribe to bot events** → **Add Bot User Event** → add `message.channels`
4. Click **Save Changes** at the bottom of the page before navigating away

> **Common mistake**: Switching tabs before clicking Save Changes resets the toggle to OFF. Always save before leaving the page.

---

## 7. Verify Everything is Working

Run the stack:

```bash
docker compose up --build
```

Then in a separate terminal, run the CLI:

```bash
python main.py "Senior Python Engineer at Acme Corp..."
```

You should see a resume review message appear in the channel with Approve / Edit / Reject buttons.

**If no message appears:**

- Check **Interactivity** is still enabled and shows **Verified ✓**
- Check ngrok is running and the URL matches what's in Slack
- Check logs: `docker compose logs app --tail=50` — look for `POST /slack/events 200`
- Check the signing secret — `SLACK_SIGNING_SECRET` in `.env` must match exactly what's shown under **Basic Information → App Credentials**

---

## Credentials Reference

After setup, your `.env` should have:

```
SLACK_BOT_TOKEN=xoxb-...        # from OAuth & Permissions
SLACK_SIGNING_SECRET=...         # from Basic Information → App Credentials
SLACK_CHANNEL_ID=C...            # right-click channel → View channel details
```
