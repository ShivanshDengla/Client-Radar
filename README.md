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

### Is Render free?

**Not for this bot.** Render's Hobby plan is **$0/month for the workspace**, but that's only the account fee. Background workers (what we need) require a **paid compute instance**:

| What | Cost |
|------|------|
| Render Hobby workspace | $0/month |
| Background Worker (Starter) | **~$7/month** |
| Free web services on Render | Yes, but they **spin down** after inactivity — bad for a polling bot |

So Render is great when you're ready to pay ~$7/mo. For personal use, use the **free option below**.

---

### Option A — GitHub Actions (FREE, recommended for personal use)

Runs one scan every **10 minutes** automatically. No server to manage.

**Limits:** GitHub may delay scheduled runs by a few minutes. On **private** repos you get 2,000 free minutes/month (plenty for this). **Public** repos get unlimited minutes.

#### Setup
1. Push your code to GitHub (make sure `.env` is NOT committed — it's in `.gitignore`).
2. On GitHub → your repo → **Settings** → **Secrets and variables** → **Actions**.
3. Click **New repository secret**:
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: your Discord webhook URL
4. Go to the **Actions** tab → enable workflows if prompted.
5. Click **Client Radar** → **Run workflow** to test immediately.

After that it runs automatically every ~10 minutes. The workflow file is already in `.github/workflows/client-radar.yml`.

To change subreddits when using GitHub Actions, edit the `SUBREDDITS` line in that workflow file.

---

### Option B — Render (~$7/month, when you want always-on)

Better if you need exact 5-minute intervals and don't want to rely on GitHub's scheduler.

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
1. Go to [render.com](https://render.com) and sign up.
2. Connect your GitHub account.

#### Step 3 — Deploy with Blueprint
1. Render dashboard → **New** → **Blueprint**.
2. Connect your `client-radar` repo.
3. Set `DISCORD_WEBHOOK_URL` when prompted.
4. Click **Apply** (~$7/mo Starter worker).

#### Step 4 — Verify
Check **Logs** in Render for fetch messages. Matches appear in Discord automatically.

---

### Option C — Run on your Mac (free, but only while it's on)

```bash
python main.py
```

Stops when you close the laptop or quit the terminal. Fine for testing, not true 24/7.

---

## Subreddits we monitor (24 communities)

| Category | Subreddits |
|----------|------------|
| Hiring / freelance boards | `forhire`, `jobbit`, `slavelabour`, `freelance_forhire`, `DoneDirtCheap`, `FreelanceProgramming`, `hireaprogrammer` |
| Web / app dev | `AppDevelopers`, `webdev`, `web_design`, `reactjs`, `nextjs`, `node`, `rails`, `django`, `Wordpress`, `Shopify` |
| Mobile | `flutterdev`, `iOSProgramming`, `androiddev` |
| Startups / business | `startups`, `Entrepreneur`, `smallbusiness`, `SaaS` |

Edit `SUBREDDITS` in your `.env` to add or remove any. Separate names with commas, no `r/` prefix.

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
