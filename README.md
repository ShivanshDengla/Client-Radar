# Reddit Client Radar

Find **web dev, app dev, and script/automation** freelance gigs on Reddit and send them to Discord.

**Manual use only** — you run it when you want (morning, lunch, evening). It remembers what it already sent so you never get duplicates.

- No Reddit account or API keys
- Anonymous public RSS feeds
- SQLite tracks seen post IDs between runs

---

## Quick start

### 1. Install (once)

```bash
cd /Users/shivanshdengla/Desktop/Client-Radar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Add Discord webhook to `.env`

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
```

Get it from Discord: channel **gear** → **Integrations** → **Webhooks** → **New Webhook** → copy URL.

### 3. Run whenever you want new leads

```bash
source .venv/bin/activate
python main.py
```

That's it. Run it again a few hours later — only **new** posts since your last run are checked.

---

## Daily routine (suggested)

```bash
# Morning — catch overnight posts
python main.py

# Afternoon / evening — catch new posts
python main.py
```

Each run:
1. Pulls the latest ~25 posts per subreddit batch from Reddit
2. Skips anything already in `seen_posts.db`
3. Sends matching **client hiring** posts to Discord
4. Sends a short green **status summary** (optional, on by default)

---

## Commands

| Command | What it does |
|---------|----------------|
| `python main.py` | Normal scan — use this |
| `python main.py --verbose` | Scan + log why each post was skipped |
| `python main.py --test-discord` | Send a fake test post to Discord |

---

## Settings (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_WEBHOOK_URL` | Yes | Your Discord webhook |
| `SUBREDDITS` | Yes | Comma-separated list, no `r/` prefix |
| `POST_FETCH_LIMIT` | No | Posts per feed (default `25`) |
| `SEND_STATUS_TO_DISCORD` | No | Summary after each run (default `true`) |

Default subreddits focus on hiring boards + dev communities. Edit `SUBREDDITS` in `.env` to change them.

---

## What gets sent to Discord

**Client posts only** — someone hiring for web/app/script work. Filtered out:

- `[For Hire]` posts (freelancers selling services)
- Discussion threads (`How do I…`, `What should I…`)
- News, advice, showcase posts
- Graphic designers, VAs, legal, etc.

---

## Files

| File | Job |
|------|-----|
| `main.py` | Run this to scan |
| `matcher.py` | Hiring filter logic |
| `reddit_client.py` | Fetches Reddit RSS |
| `discord_notifier.py` | Sends to Discord |
| `database.py` | `seen_posts.db` — no duplicate alerts |
| `config.py` | Reads `.env` |

---

## Reset seen posts

To re-check everything from scratch (e.g. after changing filters):

```bash
rm seen_posts.db
python main.py
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No Discord messages | Run `python main.py --test-discord` |
| `429` rate limit errors | Wait a minute, run again; fewer subreddits in `.env` helps |
| No matches | Normal — run `--verbose` to see skips; real hiring posts are rare |
| Wrong posts getting through | Edit filters in `matcher.py` |
