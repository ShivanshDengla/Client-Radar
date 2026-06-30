# Reddit Client Radar

Monitors Reddit communities for **people hiring software / web / app developers**
and sends matching posts to a **Discord channel** via webhook.

- **No Reddit account needed** — uses anonymous public RSS feeds
- **No API keys** — Reddit blocked self-serve API access for new developers
- **No duplicate alerts** — remembers seen post IDs in SQLite

---

## What each file does

| File | Job |
|------|-----|
| `main.py` | Entry point. Runs the check-and-notify loop. |
| `config.py` | Reads settings from `.env`. |
| `reddit_client.py` | Fetches posts via public RSS (no login). |
| `matcher.py` | Detects hiring intent, budget, dev type, keywords. |
| `discord_notifier.py` | Sends formatted messages to Discord. |
| `database.py` | Stores seen post IDs in SQLite. |
| `render.yaml` | One-click deploy config for Render hosting. |

---

## Part 1 — Discord setup (do this first)

### 1. Create a Discord server (if you don't have one)
1. Open the Discord app or [discord.com](https://discord.com).
2. Click the **+** on the left sidebar → **Create My Own** → **For me and my friends**.
3. Name it something like `Client Radar`.

### 2. Create a channel for leads
1. Right-click your server name → **Create Channel**.
2. Name it `#client-leads` (or anything you like).
3. Click **Create Channel**.

### 3. Create the webhook
1. Click the **gear icon** next to `#client-leads`.
2. Go to **Integrations** → **Webhooks** → **New Webhook**.
3. Name it `Client Radar`.
4. Make sure the correct channel is selected.
5. Click **Copy Webhook URL**.

That URL looks like:
```
https://discord.com/api/webhooks/123456789/AbCdEfGhIjKlMnOp...
```

Keep it secret — anyone with this URL can post to your channel.

---

## Part 2 — Run locally on your Mac

### 1. Install dependencies
```bash
cd /Users/shivanshdengla/Desktop/Client-Radar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create your `.env` file
```bash
cp .env.example .env
```

Open `.env` in any text editor and paste your webhook URL:
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
```

That's the **only required setting**. No Reddit keys needed.

### 3. Test Discord
```bash
python main.py --test-discord
```
Check `#client-leads` — you should see a test "New Client Post!" embed.

### 4. Test a real Reddit fetch
```bash
python main.py --once
```
This fetches live posts once and sends any matches to Discord.

### 5. Run continuously
```bash
python main.py
```
Checks every 5 minutes. Press **Ctrl+C** to stop.

---

## Part 3 — Deploy online (keep it running 24/7)

### Why not Vercel?
Vercel is built for websites, not long-running bots. This app needs to:
- Run every 5 minutes forever
- Save a SQLite database between runs

**Render** is the better fit — it runs a background worker that stays on.

Cost: Render Starter worker is about **$7/month**. There is no good free always-on option for Python bots in 2026.

### Deploy to Render (recommended)

#### Step 1 — Push code to GitHub
```bash
cd /Users/shivanshdengla/Desktop/Client-Radar
git init
git add .
git commit -m "Initial Client Radar setup"
```
Create a new repo on GitHub, then:
```bash
git remote add origin https://github.com/YOUR_USERNAME/client-radar.git
git branch -M main
git push -u origin main
```

#### Step 2 — Create a Render account
1. Go to [render.com](https://render.com) and sign up (free account is fine).
2. Connect your GitHub account.

#### Step 3 — Deploy with Blueprint
1. In Render dashboard → **New** → **Blueprint**.
2. Connect your `client-radar` GitHub repo.
3. Render reads `render.yaml` automatically.
4. Before deploying, set the secret:
   - Find `DISCORD_WEBHOOK_URL` → click **Add value** → paste your webhook URL.
5. Click **Apply**.

Render will build and start a **Background Worker** running `python main.py`.

#### Step 4 — Verify it's live
1. In Render → your service → **Logs**.
2. You should see lines like:
   ```
   Reddit Client Radar starting up (anonymous RSS — no Reddit account).
   Fetched 25 posts. (Known so far: 0)
   ```
3. When a match is found, it appears in Discord automatically.

#### Step 5 — Change settings later
In Render → **Environment**, you can edit:
- `SUBREDDITS` — which communities to watch
- `POLL_INTERVAL_SECONDS` — how often to check (default 300 = 5 min)

---

## Security — your Reddit account is safe

| What we do | What we do NOT do |
|---|---|
| Fetch public RSS feeds anonymously | Log into Reddit |
| Use a generic `User-Agent` label | Store Reddit passwords or cookies |
| Only read public post titles/bodies | Post, comment, or vote on Reddit |
| Store only post IDs in SQLite | Touch your Reddit account at all |

Your Reddit account is never involved. If Reddit blocks the RSS feed IP someday, worst case the bot stops fetching — your account is unaffected.

---

## Discord message format

Each match shows:
- **Subreddit** (e.g. `r/forhire`)
- **Title** (clickable link)
- **Age** (e.g. `2 minutes`)
- **Budget** (e.g. `$2,000` or `TBD`)
- **Client Type** (`Web Dev`, `App Dev`, `Software Dev`)
- **Keywords matched**
- **Link** to the Reddit post

---

## Customizing matches

Edit `matcher.py`:
- `HIRING_INTENT` — phrases that mean someone wants to hire
- `CATEGORY_KEYWORDS` — dev keywords by type
- `OFFERING_SIGNALS` — skip posts where people offer their own services

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Missing required setting DISCORD_WEBHOOK_URL` | Fill in `.env` or Render environment |
| `Test message FAILED` | Webhook URL is wrong or deleted — create a new one |
| `Fetched 0 posts` | Reddit RSS may be temporarily down — wait and retry |
| `403` from Reddit | Rare for RSS; try again in a few minutes |
| Duplicate notifications after redeploy | Normal on first run after a fresh deploy — SQLite resets if disk is wiped. Matches only repeat if the DB file is lost. |
