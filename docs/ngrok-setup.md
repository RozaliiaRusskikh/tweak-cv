# ngrok Setup

ngrok creates a public HTTPS tunnel to your local server so Slack can send webhook callbacks to your machine.

---

## 1. Install

```bash
brew install ngrok
```

---

## 2. Create a Free Account

1. Go to [dashboard.ngrok.com](https://dashboard.ngrok.com) and sign up
2. Copy your **Authtoken** from the dashboard

---

## 3. Authenticate

```bash
ngrok config add-authtoken <your-authtoken>
```

---

## 4. Start the Tunnel

```bash
ngrok http 3000
```

You'll see output like:

```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:3000
```

Copy the `https://` URL — this is what you paste into Slack.

---

## 5. Use in Slack

Paste the URL into both places in your Slack app settings (see [slack-setup.md](slack-setup.md)):

- **Interactivity & Shortcuts** → Request URL: `https://abc123.ngrok-free.app/slack/events`
- **Event Subscriptions** → Request URL: `https://abc123.ngrok-free.app/slack/events`

---

## Static Domain (Free)

ngrok gives every free account **one free static domain** — the URL never changes, so you only configure Slack once.

1. Go to [dashboard.ngrok.com/domains](https://dashboard.ngrok.com/domains)
2. Click **New Domain** — ngrok generates a free static domain for you
3. Start the tunnel using that domain:

```bash
ngrok http --url=<your-static-domain> 3000
```

Add it to `.env`:

```
PUBLIC_URL=https://<your-static-domain>
```

Use `PUBLIC_URL` in your Slack app settings — you never need to update it again.

---

## Important

- ngrok must be running whenever you use the bot. Start it before `docker compose up`.
- With a static domain, the Slack URLs never need updating between restarts.
