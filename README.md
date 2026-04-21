# X Deal Sourcing

A deal-sourcing pipeline that identifies influential figures and emerging projects in the startup and crypto ecosystem by monitoring who accounts on a curated watchlist are newly following on X (Twitter).

## How It Works

Each weekly run:
1. Fetches accounts that each watchlist member started following in the last 7 days (via Sorsa API)
2. Aggregates results — surfaces accounts followed by the most watchlist members
3. Enriches each new account with full profile data and their last 20 tweets
4. Analyzes tweets with AI (Groq / LLaMA) to generate a description, extract mentioned entities, and classify the account as `project` or `person`
5. Syncs all new accounts to a Notion dashboard
6. Sends a Telegram digest of newly discovered projects (created within the last 2 years), sorted by watchlist follower count

## Notion Dashboard

Each account entry includes:
- Name + X profile link
- Account ID and username
- Account creation date
- Watcher count + list of watchlist accounts that follow them
- Official bio
- AI-generated description based on last 20 tweets
- Mentioned entities (projects, tokens, VCs, people)
- Followers count, friends count, tweets count
- Last tweet date
- Verified status
- Account type (project / person)

## Setup

### Prerequisites
- Python 3.10+
- [Sorsa API](https://sorsa.io) key
- [Groq](https://console.groq.com) API key (free tier)
- Notion integration token + database
- Telegram bot token + group chat ID

### Installation

```bash
git clone https://github.com/DarkoIOSG/X-deal-sourcing.git
cd X-deal-sourcing
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```
TweetScout_API_key=your_sorsa_api_key
OPENAI_API_key=your_openai_api_key
GROQ_API_KEY=your_groq_api_key
NOTION_TOKEN=your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_group_chat_id
```

### Watchlist

Add X profile URLs (one per line) to `followed_accounts.txt`:

```
https://x.com/username1
https://x.com/username2
```

### Notion Database

Create a Notion database with these properties:

| Property | Type |
|---|---|
| Name | Title |
| X Profile | URL |
| Account ID | Text |
| Username | Text |
| Account Created | Date |
| Watcher Count | Number |
| Watchers | Text |
| Official Bio | Text |
| Tweet Analysis | Text |
| Entities | Text |
| Followers Count | Number |
| Friends Count | Number |
| Tweets Count | Number |
| Last Tweet Date | Date |
| Verified | Checkbox |
| Account Type | Select (project / person / unknown) |

Connect the Notion integration to the database via **Settings → Connections**.

## Usage

```bash
python3 run.py
```

State is stored in `state.db` (SQLite). Accounts already synced to Notion are skipped on subsequent runs — only new discoveries are processed each week.

To reset and reprocess everything:
```bash
rm state.db
```

## Project Structure

```
run.py                    # entry point
config.py                 # environment variables and constants
state.py                  # SQLite state management
api/
  sorsa.py                # Sorsa API v3 client
  notion.py               # Notion API client
pipeline/
  fetch_following.py      # fetch new follows (7d) for each watchlist account
  aggregate.py            # find accounts followed by multiple watchlist members
  enrich.py               # enrich profiles and fetch tweets
  analyze.py              # AI tweet analysis via Groq
  notion_sync.py          # sync new accounts to Notion
  telegram_notify.py      # send Telegram digest of new projects
```
