# X Deal Sourcing Pipeline

An end-to-end deal-sourcing system for IOSG Ventures. Discovers new crypto projects across multiple channels, scores them against the fund's investment thesis using Claude AI, and produces one-page investment memos for the best candidates — all synced to a Notion dashboard.

---

## Workflow

### Daily — Discovery

Run all five scripts every day. Each script pushes new projects to Notion with `Status = New`.

```bash
python3 scripts/search_x.py               # X keyword search (launch announcements)
python3 scripts/search_linkedin.py --push  # LinkedIn funding announcements via Exa
python3 scripts/search_github.py --push    # GitHub new crypto repos
python3 scripts/search_google_news.py --push  # Google News RSS funding signals
python3 scripts/fetch_defillama_raises.py  # DeFi Llama recent raises
```

### Weekly — Scoring

```bash
python3 run_watchlist.py  # Smart money watchlist: who is the smart money newly following?
python3 run_score.py      # Phase 1 hard filter + Phase 2 AI scoring on all Status = New
```

### After Scoring — Deep Dive

1. Open Notion, filter for `Status = Scored, Recommendation = deep_dive`
2. For each project, run this prompt in Claude (web_search + web_fetch only):

```
Deep-dive @{handle}. Follow shared/prompts/deep_dive_manual.md for steps
and shared/prompts/memo_format.md for the memo format.
Never use Anthropic API — web_search and web_fetch only.
```

3. Share the resulting list with your recommendation: **WATCH** or **TAKE MEETING**

---

## Pipeline Overview

```
Daily discovery
    ├── scripts/search_x.py               ← X keyword search
    ├── scripts/search_linkedin.py        ← LinkedIn posts via Exa
    ├── scripts/search_github.py          ← GitHub new repos
    ├── scripts/search_google_news.py     ← Google News RSS
    └── scripts/fetch_defillama_raises.py ← DeFi Llama raises

Weekly
    └── run_watchlist.py         ← Smart money watchlist (who is smart money following?)

All sources → Notion (Status = New)
    │
    ▼
run_score.py
    ├── Phase 1: hard filter  →  Status = Filtered
    └── Phase 2: AI scoring   →  Status = Scored

Manual deep dive (Claude, web only)
    └── Memo per project  →  WATCH / TAKE MEETING
```

---

## Discovery Scripts

### `scripts/search_x.py` — X Keyword Search

Searches X for recent tweets matching launch/announcement keywords in the crypto space.

- Searches for terms like `"waitlist open"`, `"launching beta"`, `"alpha access"` + crypto keywords
- Filters by minimum likes (20) and minimum followers (200)
- Classifies each account with Claude Haiku (project vs. person, sector, stage)
- Pushes new projects to Notion with `Status = New`

```bash
python3 scripts/search_x.py
```

---

### `scripts/search_linkedin.py` — LinkedIn via Exa

Queries Exa restricted to `linkedin.com` for funding announcements and product launches. LinkedIn founder posts are a distinct signal — first-person raises often appear here before news coverage.

- 14 queries covering seed rounds, pre-seed, launches across DeFi/web3 themes
- Company name extracted from post titles using headline patterns + LinkedIn-specific patterns (`"Introducing X"`, `"X's $5M seed"`, `"doing at X"`)
- 4-layer X handle resolution: article page → Exa X-profile search → Sorsa tweet search → Exa company search

```bash
python3 scripts/search_linkedin.py           # preview only
python3 scripts/search_linkedin.py --push    # resolve handles + push to Notion
```

---

### `scripts/search_github.py` — GitHub Repos

Searches GitHub for newly created or recently pushed repositories matching crypto/web3 keywords.

- Covers keywords: `defi protocol`, `prediction market`, `stablecoin`, `perpetuals dex`, `onchain payments`, `rwa tokenization`, `ai agent defi`, plus alt ecosystems (Arc, Canton, Tempo)
- Filters by minimum 5 stars and non-fork repos created in the last 90 days
- Resolves X handle from: GitHub owner profile → repo homepage → README → Exa company search

```bash
python3 scripts/search_github.py             # preview only
python3 scripts/search_github.py --push      # resolve handles + push to Notion
```

---

### `scripts/search_google_news.py` — Google News RSS

Monitors Google News RSS feeds for funding announcements and product launches.

- 16 queries covering seed rounds, launches, and specific protocol themes
- Company name extracted from news headlines via action-verb splitting
- Same 4-layer X handle resolution as LinkedIn script

```bash
python3 scripts/search_google_news.py           # preview only
python3 scripts/search_google_news.py --push    # resolve handles + push to Notion
```

---

### `scripts/fetch_defillama_raises.py` — DeFi Llama Raises

Pulls recent raises from the DeFi Llama fundraising API.

```bash
python3 scripts/fetch_defillama_raises.py
```

---

### `run_watchlist.py` — Watchlist Tracking (Weekly)

Monitors who the smart money on X is newly following. Surfaces projects followed by multiple respected accounts in the last 7 days.

1. Reads watchlist from `followed_accounts.txt` (one X profile URL per line)
2. Fetches new follows (last 7 days) per watchlist member via Sorsa API
3. Aggregates — surfaces accounts followed by most watchlist members first
4. Skips accounts already in `state.db`
5. Enriches profiles + last 20 tweets
6. Classifies with Claude Haiku
7. Syncs to Notion with `Status = New` + sends Telegram digest

```bash
python3 run_watchlist.py
```

---

## Scoring — `run_score.py`

Pulls all `Status = New` rows from Notion and runs two filters.

### Phase 1 — Hard Filter

| Drop reason | Criteria |
|---|---|
| `person` | Account type classified as a person |
| `stale_tweets` | Last tweet > 12 months ago |
| `no_tweet_date` | No tweet date recorded |
| `excluded_sector` | Sector is L1, L2, Gaming, or NFT |

Dropped projects → `Status = Filtered` with reason recorded.

### Phase 2 — AI Scoring (Claude Haiku)

Scores each surviving project against `shared/prompts/thesis_doc.md`:

| Field | Description |
|---|---|
| `thesis_fit_score` | 0–100 score |
| `primary_thesis_match` | Named thesis category |
| `category_fit` | strong / moderate / weak / none |
| `investment_pattern_matches` | Named yes-patterns |
| `pass_pattern_matches` | Named pass-patterns / anti-patterns |
| `hard_disqualifiers` | Any triggered disqualifiers |
| `top_reasons` | 3 reasons grounded in tweets |
| `top_red_flags` | Up to 3 concerns |
| `recommendation` | `deep_dive` / `watch` / `pass` |
| `one_line_summary` | One-line pitch |

All scored projects → `Status = Scored`.

```bash
python3 run_score.py
```

---

## Deep Dive (Manual)

After scoring, filter Notion for `Status = Scored, Recommendation = deep_dive`. For each project, run this prompt in Claude:

```
Deep-dive @{handle}. Follow shared/prompts/deep_dive_manual.md for steps
and shared/prompts/memo_format.md for the memo format.
Never use Anthropic API — web_search and web_fetch only.
```

The memo follows `shared/prompts/memo_format.md`. After reviewing all memos, share the shortlist with a recommendation of **WATCH** or **TAKE MEETING** for each project.

---

## Notion Dashboard

All projects flow through one Notion database:

| Property | Type | Description |
|---|---|---|
| Name | Title | Project display name |
| Username | Text | X handle |
| X Profile | URL | Link to X profile |
| Account ID | Number | X account ID |
| Status | Select | `New` → `Scored` / `Filtered` |
| Score | Number | Thesis fit score (0–100) |
| Recommendation | Select | `deep_dive` / `watch` / `pass` |
| Scoring_JSON | Text | Full Phase 2 JSON |
| Memo | Text | Deep-dive memo (markdown) |
| Sector | Multi-select | DeFi, AI, Infrastructure, RWA, etc. |
| Stage | Select | pre-seed / seed / growth / unknown |
| Token Status | Select | has token / TGE planned / no token / unknown |
| One-liner | Text | AI-generated one-line pitch |
| Official Bio | Text | X bio |
| Tweet Analysis | Text | AI account description |
| Followers Count | Number | |
| Last Tweet Date | Date | |
| Watcher Count | Number | How many watchlist members follow this |
| Watchers | Text | Which watchlist members follow this |
| Filtered_Reason | Text | Phase 1 drop reason |
| IC_Decision | Select | Post-meeting IC decision |
| IC_Why | Text | IC reasoning |
| IC_Date | Date | IC discussion date |

---

## Setup

### Prerequisites

- Python 3.10+
- [Sorsa / TweetScout](https://tweetscout.io) API key
- [Anthropic](https://console.anthropic.com) API key
- [Exa](https://exa.ai) API key
- Notion integration token + database ID
- Telegram bot token + chat ID (optional)

### Installation

```bash
git clone https://github.com/DarkoIOSG/X-deal-sourcing.git
cd X-deal-sourcing
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```
TweetScout_API_key=your_sorsa_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
EXA_API_KEY=your_exa_api_key
NOTION_TOKEN=your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_group_chat_id
```

### Notion Setup

1. Create a Notion database with the properties listed above
2. Create a Notion integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
3. Connect the integration to your database via **Settings → Connections**
4. Copy the database ID from the URL: `notion.so/{workspace}/{DATABASE_ID}?v=...`

---

## Project Structure

```
run_daily.py                      # Daily: runs all discovery scripts in sequence
run_watchlist.py                  # Weekly: smart money watchlist tracking
run_score.py                      # Weekly: Phase 1 filter + Phase 2 AI scoring
run_deep_dive.py                  # On-demand: deep-dive agent on top candidates

config.py                         # API keys and constants
state.py                          # SQLite dedup (state.db)

api/
  sorsa.py                        # Sorsa / TweetScout API client
  notion.py                       # Low-level Notion API client

pipeline/
  fetch_following.py              # Fetch new follows (7d) per watchlist account
  enrich.py                       # Enrich profiles + fetch tweets
  analyze.py                      # Classify accounts with Claude Haiku
  notion_sync.py                  # Sync enriched accounts to Notion
  telegram_notify.py              # Telegram digest
  score_filter.py                 # Phase 1 hard filter logic
  score.py                        # Phase 2 Claude Haiku scoring

scripts/
  search_x.py                     # Daily: X keyword search (launch/announce signals)
  search_linkedin.py              # Daily: LinkedIn announcements via Exa
  search_github.py                # Daily: GitHub new crypto repos
  search_google_news.py           # Daily: Google News RSS funding signals
  fetch_defillama_raises.py       # Daily: DeFi Llama raises
  enrich_funding.py               # Weekly: populate funding fields (DeFiLlama + Surf)
  monitor_founders.py             # On-demand: stealth founder departure signals
  search_thematic.py              # Thematic deep search (Exa + YC + X)
  build_ic_index.py               # Build IC retrieval vector index
  test_exa.py                     # Debug Exa results for a company name

shared/
  notion.py                       # High-level Notion wrapper
  ic_retrieval.py                 # Voyage AI vector search over IC transcripts
  prompts/
    thesis_doc.md                 # IOSG investment thesis (used by scorer)
    deep_dive_manual.md           # Deep-dive research checklist (used manually)
    memo_format.md                # Memo output format (used manually)
    agent_system.txt              # Legacy agent system prompt

data/
  ic_transcripts/                 # IC meeting transcripts (gitignored)
  research/                       # Fund research papers (gitignored)
  ic_index.pkl                    # Vector index (gitignored)
  agent_logs/                     # Deep-dive traces (gitignored)
```
