# X Deal Sourcing Pipeline

An end-to-end deal-sourcing system for IOSG Ventures. Discovers new crypto projects on X (Twitter), scores them against the fund's investment thesis using Claude AI, and produces one-page investment memos for the best candidates — all synced to a Notion dashboard.

---

## How It Works — Pipeline Overview

```
X (Twitter)
    │
    ├── run.py            ← Watchlist tracking (who is the smart money following?)
    └── search_test.py    ← Keyword search (launch announcements, beta access, etc.)
    │
    ▼
Notion Dashboard  (Status = New)
    │
    ▼
score_run.py      ← Phase 1: hard filter  →  Status = Filtered
                  ← Phase 2: AI scoring   →  Status = Scored
    │
    ▼
deep_dive_run.py  ← Phase 3: agent memo   →  Status = Deep_Dived
    │
    ▼
IC team reviews memo in Notion
```

There are three independent entry points for data collection (`run.py`, `search_test.py`), one for scoring (`score_run.py`), and one for deep dives (`deep_dive_run.py`). They are designed to be run in sequence but are decoupled — you can run any step independently.

---

## Data Collection

### 1. Watchlist Tracking — `run.py`

Monitors who the smart money on X is newly following. Surfaces projects that multiple respected accounts started following in the last 7 days.

**What it does:**
1. Reads the watchlist from `followed_accounts.txt` (one X profile URL per line)
2. Fetches every account each watchlist member started following in the last 7 days (via TweetScout/Sorsa API)
3. Aggregates results — surfaces accounts followed by the most watchlist members first
4. Skips accounts already in `state.db` (SQLite dedup)
5. Enriches each new account: full profile data + last 20 tweets
6. Classifies each account with Claude Haiku: project vs. person, sector, stage, token status, one-liner
7. Syncs all new accounts to Notion with `Status = New`
8. Sends a Telegram digest of new projects

**Run:**
```bash
python3 run.py
```

**Watchlist file (`followed_accounts.txt`):**
```
https://x.com/username1
https://x.com/username2
```

---

### 2. Keyword Search — `search_test.py`

Searches X for recent tweets matching launch/announcement keywords in the crypto space. Finds projects actively announcing themselves, not just ones followed by smart money.

**What it does:**
1. Searches X for tweets matching terms like `"waitlist open"`, `"launching beta"`, `"alpha access"` combined with crypto keywords
2. Filters by minimum likes (20) and minimum followers (200)
3. Analyzes each tweet + author bio with Claude Haiku
4. Pushes new projects (type = `project`, not already in `state.db`) to Notion with `Status = New`

**Run:**
```bash
python3 search_test.py
```

To adjust search terms, edit the `KEYWORDS` list and `MIN_LIKES` / `MIN_FOLLOWERS` thresholds at the top of the file.

---

## Scoring Pipeline — `score_run.py`

Pulls all `Status = New` rows from Notion and runs them through two filters.

### Phase 1 — Hard Filter

Drops projects that clearly don't fit without calling the AI:

| Reason | Criteria |
|---|---|
| `person` | Account type classified as a person, not a project |
| `stale_tweets` | Last tweet was more than 12 months ago |
| `no_tweet_date` | No tweet date recorded |
| `excluded_sector` | Sector is L1, L2, Gaming, or NFT |

Dropped projects are marked `Status = Filtered` in Notion with the drop reason recorded.

### Phase 2 — AI Scoring

Passes each surviving project to **Claude Haiku** with the full IOSG investment thesis (`thesis.md`). Returns structured JSON:

| Field | Description |
|---|---|
| `thesis_fit_score` | 0–100 score against the thesis |
| `primary_thesis_match` | Named thesis from the thesis doc |
| `category_fit` | strong / moderate / weak / none |
| `investment_pattern_matches` | Named yes-patterns from the thesis |
| `pass_pattern_matches` | Named pass-patterns or anti-patterns |
| `hard_disqualifiers` | Any hard disqualifiers triggered |
| `top_reasons` | 3 specific reasons grounded in tweets |
| `top_red_flags` | Up to 3 concerns grounded in tweets |
| `recommendation` | `deep_dive` / `watch` / `pass` |
| `one_line_summary` | One-line pitch in fund vocabulary |

All scored projects are written back to Notion with `Status = Scored`.

**Run:**
```bash
python3 score_run.py
```

---

## Deep Dive Agent — `deep_dive_run.py`

Pulls all `Status = Scored, Recommendation = deep_dive` rows from Notion and runs an autonomous research agent on each.

**The agent (Claude Opus 4.7) has three tools:**

| Tool | What it does |
|---|---|
| `web_search` | Searches the web for current information (max 8 uses) |
| `web_fetch` | Fetches the content of a specific URL (max 5 uses) |
| `retrieve_ic_context` | Searches past IC meeting transcripts and fund research for prior discussions of similar deals (custom, uses local vector index) |

**What the agent investigates (from the system prompt checklist):**
1. Finds the project's website and reads it
2. Identifies the team — named founders, track record
3. Checks funding history — prior raises, investors, valuation
4. Verifies the product exists — code repos, audits, deployed contracts, real usage
5. Checks for rebrands of dead projects, recycled teams, controversies
6. Calls `retrieve_ic_context` 2–3 times to surface prior IC discussions of similar projects or sectors

**Output — one-page markdown memo with:**
- Recommendation: Take meeting / Watch / Pass
- Thesis fit + confidence
- What it is
- Why it fits the thesis
- What checks out (external evidence)
- What concerns me (red flags)
- Comparable past IC discussions (with source file and date)
- Open questions for a first meeting
- Sources

The memo is written to the `Memo` field in Notion and `Status` is set to `Deep_Dived`. The full agent trace (every tool call and result) is saved to `data/agent_logs/{timestamp}_{handle}.json`.

**Run:**
```bash
python3 deep_dive_run.py            # all deep_dive candidates
python3 deep_dive_run.py --limit 3  # top 3 by score only
python3 deep_dive_run.py --dry-run  # preview candidates without calling the agent
```

---

## IC Retrieval Index

The deep-dive agent can search past IC meeting transcripts and fund research using semantic vector search. The index must be built once (and rebuilt whenever new transcripts are added).

**Supported source folders:**

| Folder | Content |
|---|---|
| `data/ic_transcripts/` | IC meeting transcripts (.txt or .md, filename should contain a date like `2024-03-15`) |
| `data/research/` | Fund research papers and memos (.txt or .md) |

**Build the index:**
```bash
python3 scripts/build_ic_index.py
```

This chunks all documents into ~3200-character segments with 400-character overlap, embeds them with Voyage AI (`voyage-4-lite`, multilingual EN+ZH), and saves the index to `data/ic_index.pkl`.

Rebuild whenever you add new transcripts or research. The index file is gitignored — each machine that runs the deep-dive agent needs its own copy.

**Test retrieval quality:**
```bash
python3 scripts/test_retrieval.py
```

---

## Notion Dashboard

All projects flow through one Notion database. Key properties:

| Property | Type | Description |
|---|---|---|
| Name | Title | Project display name |
| Username | Text | X handle |
| X Profile | URL | Link to X profile |
| Account ID | Number | X account ID |
| Status | Select | `New` → `Scored` / `Filtered` → `Deep_Dived` → `Reviewed` → `Decided` |
| Score | Number | Phase 2 thesis fit score (0–100) |
| Recommendation | Select | `deep_dive` / `watch` / `pass` |
| Scoring_JSON | Text | Full Phase 2 JSON output |
| Memo | Text | Deep-dive agent memo (markdown) |
| Sector | Multi-select | DeFi, AI, Infrastructure, RWA, etc. |
| Stage | Select | pre-seed / seed / growth / unknown |
| Token Status | Select | has token / TGE planned / no token / unknown |
| One-liner | Text | AI-generated one-line pitch |
| Official Bio | Text | X bio |
| Tweet Analysis | Text | AI-generated account description |
| Followers Count | Number | |
| Last Tweet Date | Date | |
| Watcher Count | Number | How many watchlist members follow this account |
| Watchers | Text | Which watchlist members follow this account |
| Filtered_Reason | Text | Why it was filtered in Phase 1 |
| IC_Decision | Select | Post-meeting IC decision |
| IC_Why | Text | IC reasoning |
| IC_Date | Date | Date of IC discussion |

---

## Setup

### Prerequisites

- Python 3.10+
- [TweetScout/Sorsa](https://tweetscout.io) API key
- [Anthropic](https://console.anthropic.com) API key
- [Voyage AI](https://dash.voyageai.com) API key (for IC retrieval index)
- Notion integration token + database ID
- Telegram bot token + chat ID (optional, for digest notifications)

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
VOYAGE_API_KEY=your_voyage_api_key
NOTION_TOKEN=your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_group_chat_id
```

### Notion Setup

1. Create a Notion database with the properties listed in the table above
2. Create a Notion integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
3. Connect the integration to your database via the database's **Settings → Connections** menu
4. Copy the database ID from the URL: `notion.so/{workspace}/{DATABASE_ID}?v=...`

### IC Index Setup

1. Place IC meeting transcripts in `data/ic_transcripts/` (filenames should include a date, e.g. `IC_2024-03-15_session.txt`)
2. Place fund research in `data/research/`
3. Run:
```bash
python3 scripts/build_ic_index.py
```

---

## Project Structure

```
run.py                          # Data collection: watchlist tracking
search_test.py                  # Data collection: keyword search
score_run.py                    # Phase 1 filter + Phase 2 AI scoring
deep_dive_run.py                # Phase 3 deep-dive agent

config.py                       # Environment variables and constants
state.py                        # SQLite dedup (state.db)

api/
  sorsa.py                      # TweetScout/Sorsa API client
  notion.py                     # Low-level Notion API client (used by run.py / search_test.py)

pipeline/
  fetch_following.py            # Fetch new follows (7d) per watchlist account
  aggregate.py                  # Aggregate across watchlist, find new accounts
  enrich.py                     # Enrich profiles and fetch tweets
  analyze.py                    # Classify accounts with Claude Haiku
  notion_sync.py                # Sync enriched accounts to Notion
  telegram_notify.py            # Telegram digest
  score_filter.py               # Phase 1 hard filter logic
  score.py                      # Phase 2 Claude Haiku scoring

shared/
  notion.py                     # High-level Notion wrapper (used by score_run / deep_dive)
  ic_retrieval.py               # Voyage AI vector search over IC index
  prompts/
    thesis_doc.md               # Active IOSG investment thesis (used by deep-dive agent)
    agent_system.txt            # Deep-dive agent system prompt

deep_dive/
  agent.py                      # Claude Opus 4.7 agent loop

scripts/
  build_ic_index.py             # Build/rebuild the IC retrieval vector index
  test_deep_dive.py             # Test the deep-dive agent on a single hardcoded project
  test_notion_wrapper.py        # Test shared/notion.py read/write round-trip
  test_retrieval.py             # Test IC retrieval quality with sample queries

data/
  ic_transcripts/               # IC meeting transcripts (gitignored)
  research/                     # Fund research papers (gitignored)
  ic_index.pkl                  # Built vector index (gitignored)
  agent_logs/                   # Deep-dive agent traces, one JSON file per run (gitignored)
```

---

## Running the Full Pipeline

A typical weekly workflow:

```bash
# 1. Collect new projects
python3 run.py          # watchlist-based discovery
python3 search_test.py  # keyword-based discovery

# 2. Score everything new in Notion
python3 score_run.py

# 3. Run deep dives on top candidates
python3 deep_dive_run.py --limit 5

# 4. Review memos in Notion, update IC_Decision + IC_Why
```

---

## Testing

```bash
# Test Notion read/write
python3 scripts/test_notion_wrapper.py

# Test IC retrieval quality
python3 scripts/test_retrieval.py

# Test full deep-dive agent on one project (edit TEST_PROJECT first)
python3 scripts/test_deep_dive.py
```
