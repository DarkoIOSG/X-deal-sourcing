# IOSG Deal Sourcing System — Overview

## What We Built

An automated crypto deal-sourcing pipeline that monitors data sources daily, scores projects against our investment thesis using AI, and produces research memos for the team to review and vote on.

**Three Parts:**
1. **Discovery + Scoring Pipeline** — Python scripts, runs on local machine
2. **Deep-Dive Agent** — Claude/Codex agent accessible via Discord, runs on MacMini
3. **Voting Dashboard** — Web app deployed on Vercel, team votes on scored projects

---

## App 1: Discovery + Scoring Pipeline

The core engine. Runs as scheduled Python scripts — no server needed.

```
┌─────────────────────────────────────────────────────────────────┐
│                    DISCOVERY PIPELINE (Daily)                   │
│                       run_daily.py                              │
└──────────┬────────────┬───────────────┬──────────┬──────────────┘
           │            │               │          │
           ▼            ▼               ▼          ▼
   ┌───────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────────────┐
   │    X        │  GitHub  │ │ Google News  │ │   LinkedIn       │
   │  search   │ │  repos   │ │  RSS feeds   │ │   via Exa search │
   │           │ │          │ │              │ │                  │
   │ "waitlist │ │new crypto│ │ "raises $XM" │ │ "announces seed" │
   │  open"    │ │ repos,   │ │ "launches"   │ │ "new product"    │
   │ "now live"│ │ ≥5 stars │ │ 16 queries   │ │ 14 queries       │
   └─────┬─────┘ └────┬─────┘ └──────┬───────┘ └────────┬─────────┘
         │            │              │                  │
         └────────────┴──────────────┴──────────────────┘
                                     │
                       ┌─────────────▼─────────────┐
                       │   DeFi Llama fundraising  │
                       │   (raises last 30 days)   │
                       └─────────────┬─────────────┘
                                     │
                       ┌─────────────▼─────────────┐
                       │  Handle Resolution        │
                       │  X handle lookup via:     │
                       │  1. URL/metadata extract  │
                       │  2. Exa X-profile search  │
                       │  3. Sorsa tweet search    │
                       │  4. Exa company search    │
                       └─────────────┬─────────────┘
                                     │
                       ┌─────────────▼─────────────┐
                       │  Claude Haiku (fast AI)   │
                       │  Classifies each project: │
                       │  • type (project/person)  │
                       │  • sector (DeFi/AI/RWA…)  │
                       │  • X account infos        │
                       │  • one-liner              │
                       └─────────────┬─────────────┘
                                     │
                       ┌─────────────▼─────────────┐
                       │      NOTION DATABASE      │
                       │       Status = "New"      │
                       └───────────────────────────┘


┌─────────────────────────────────────────────────────────────────┐
│              SMART MONEY WATCHLIST (Weekly: run_watchlist.py)   │
└─────────────────────────────────────────────────────────────────┘
                             │
         ┌───────────────────▼───────────────────┐
         │  followed_accounts.txt                │
         │  ~600 top crypto investors/founders.  │
         │  tracked on X                         │
         └───────────────────┬───────────────────┘
                             │
         ┌───────────────────▼───────────────────┐
         │  Sorsa API: new follows (last 7 days) │
         │  "Who did @top_investor just follow?" │
         └───────────────────┬───────────────────┘
                             │
         ┌───────────────────▼───────────────────┐
         │  SQLite deduplication                 │
         │  (skip accounts seen in past runs)    │
         └───────────────────┬───────────────────┘
                             │
         ┌───────────────────▼───────────────────┐
         │  Enrich + Classify (same as above)    │
         │Add: watcher_count, which watchers etc.│
         └───────────────────┬───────────────────┘
                             │
         ┌───────────────────▼───────────────────┐
         │         NOTION DATABASE               │
         │   Status = "New" + Watcher data       │
         └───────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────┐
│               SCORING PIPELINE (Weekly: run_score.py)           │
└─────────────────────────────────────────────────────────────────┘

  Notion (Status=New)
         │
         ▼
  ┌─────────────────────────┐
  │ PHASE 1: Hard Filters   │  ──drop──▶  Notion (Status=Filtered)
  │ ✗ person accounts       │
  │ ✗ stale (>12mo tweets)  │
  │ ✗ L1 / L2 / Gaming / NFT│
  └─────────┬───────────────┘
            │ pass
            ▼
  ┌─────────────────────────┐
  │  PHASE 2: AI Scoring    │
  │  Claude Haiku reads:    │
  │  • thesis_doc.md (9     │
  │    investment theses)   │
  │  • project tweets + bio │
  │                         │
  │ Returns JSON:           │
  │ • thesis_fit_score 0-100│
  │ • primary_thesis_match  │
  │ • init recommendation:  │
  │   deep_dive/watch/pass  │
  │ • top_reasons (3)       │
  │ • top_red_flags (3)     │
  └─────────┬───────────────┘
            │
            ▼
  Notion (Status=Scored, Scoring_JSON)


┌─────────────────────────────────────────────────────────────────┐
│               FUNDING ENRICHMENT (Weekly: enrich_funding.py)    │
└─────────────────────────────────────────────────────────────────┘

       Notion
         │
         ▼
  ┌─────────────────────────────────────────┐
  │  Layer 1: DeFi Llama full raises DB     │
  │  Match by project name                  │
  └─────────────┬───────────────────────────┘
                │ not found
                ▼
  ┌─────────────────────────────────────────┐
  │  Layer 2: Surf API by Twitter handle    │
  └─────────────┬───────────────────────────┘
                │
                ▼
  Notion: Raised, Last Round Date, Amount,
          Valuation, Investors fields updated


DATA STORES
───────────
• Notion database — source of truth, all 30+ fields per project
• SQLite (state.db) — deduplication, run logs, team votes
  - known_accounts: every X account ID ever seen (prevents re-processing)
  - run_log: audit trail of each pipeline run
  - votes: team voting results (synced to Notion)
```

**External APIs used:**
| Service | What for |
|---|---|
| Sorsa (TweetScout) | X/Twitter data — search, profiles, follower data |
| Anthropic (Claude Haiku) | Fast classification and thesis scoring |
| Exa | Web search for LinkedIn, GitHub discovery, handle lookup |
| DeFi Llama Pro | Fundraising data feed |
| GitHub API | New crypto repo discovery |
| Surf API | Project intelligence fallback for funding data |
| Voyage AI | Vector embeddings for IC transcript search |
| Notion API | Project database (source of truth) |
| Google News RSS | Free news feed for launch/raise announcements |

---

## App 2: Deep-Dive Agent (Discord + MacMini)

An AI research agent that produces full investment memos on demand. Runs locally on MacMini, accessible by the team through Discord.

```
┌─────────────────────────────────────────────────────────────────┐
│                      DISCORD INTERFACE                          │
│                     (runs on MacMini)                           │
└─────────────────────────────────────────────────────────────────┘

  Type in Discord:
  "Deep-dive (list of handles). Follow shared/prompts/deep_dive_manual.md
   for steps and shared/prompts/memo_format.md for format.
   Never use Anthropic API — web_search and web_fetch only."
         │
         ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  CLAUDE OPUS/CODEX AGENT                                    │
  │  System prompt: shared/prompts/agent_system.txt             │
  │                                                             │
  │  Tools available:                                           │
  │  • web_search  (max 8 calls per memo)                       │
  │  • web_fetch   (max 5 calls per memo)                       │
  │  • retrieve_ic_context (vector search over IC history)      │
  └─────────────────────────────────────────────────────────────┘
         │
         │  Follows deep_dive_manual.md checklist:
         │
         ├──▶ 1. Find fresh tweets (last 2 weeks)
         │         web_search: "from:@handle since:2024-01-01"
         │
         ├──▶ 2. Team research
         │         web_search: founders, LinkedIn, prior work
         │
         ├──▶ 3. Product research
         │         web_fetch: official site, docs, GitHub
         │
         ├──▶ 4. Funding & investors
         │         web_search: Crunchbase, news, DeFiLlama
         │
         ├──▶ 5. Traction signals
         │         web_search: TVL, users, GitHub activity
         │
         ├──▶ 6. Competitive landscape
         │         web_search: comparable projects, VC views
         │
         ├──▶ 7. IC context check
         │         retrieve_ic_context: "similar to X"
         │         ← pulls from 69 IC transcripts + 46 research papers
         │            indexed by Voyage AI embeddings (data/ic_index.pkl)
         │
         └──▶ 8. Produce memo
                   Format per memo_format.md:
                   • Header (name, round, amount, investors)
                   • TL;DR
                   • Team
                   • Product
                   • Traction
                   • Thesis Fit
                   • Red Flags
                   • IOSG Angle & Check Size


  ┌────────────────────────────────┐
  │  IC KNOWLEDGE BASE             │
  │  data/ic_transcripts/ (69 files)│
  │  data/research/ (46 files)      │
  │                                │
  │  Pre-indexed with Voyage AI    │
  │  → data/ic_index.pkl (13MB)    │
  │                                │
  │  Enables: "have we looked at   │
  │  something similar before?"    │
  └────────────────────────────────┘
```

**Key design choice:** Agent uses only `web_search` + `web_fetch` — no Anthropic API calls for data fetching. This keeps research grounded in real-time public information, not training data and low cost since we already have subs for Claude and Codex.

---

## App 3: Voting Dashboard (Web App on Vercel)

A lightweight team voting interface. Projects flow in automatically after scoring; team members vote up/down; partners assign for follow-up.

```
  NOTION (Status=Scored)
         │ auto-populated by pipeline
         ▼
  ┌─────────────────────────────────────────────────────────────┐
  │            VOTING DASHBOARD (vercel deploy)                 │
  │                                                             │
  │  Auth: Google OAuth → @iosg.vc emails only                  │
  │  Stack: FastAPI (Python) + React SPA                        │
  └────────────────────────────┬────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
  ┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
  │  Team View  │     │  Partners View  │     │  API Layer   │
  │             │     │                 │     │              │
  │  See all    │     │  Same + ability │     │ /api/projects│
  │  Scored     │     │  to assign      │     │ /api/vote    │
  │  projects   │     │  projects to    │     │ /api/assign  │
  │             │     │  team members   │     │ /api/me      │
  │  Vote ▲ ▼   │     │                 │     │ /api/config  │
  │  per project│     │  Partners:      │     │              │
  │             │     │  Jocy, Momir    │     └──────────────┘
  │  Team:      │     └─────────────────┘
  │  Darko, Jocy│
  │  Momir      │
  │  Yiping     │
  │  Frank      │
  │  Mario      │
  └──────┬──────┘
         │ votes recorded
         ▼
  ┌─────────────────────────┐
  │  SQLite votes table     │  ←── persists across sessions
  │  (state.db)  │
  └──────────┬──────────────┘
             │ synced
             ▼
  ┌─────────────────────────┐
  │  NOTION                 │
  │  Vote_Up, Vote_Down     │
  │  Voters (JSON dict)     │
  │  Vote_Reviewed checkbox │
  └─────────────────────────┘
```

---

## Full System Data Flow

```
╔═══════════════════════════════════════════════════════════════════╗
║                    COMPLETE DATA FLOW                            ║
╚═══════════════════════════════════════════════════════════════════╝

SOURCES                    PIPELINE                    OUTPUTS
──────                     ────────                    ───────

X/Twitter ──────────────┐
GitHub repos ───────────┤  run_daily.py (DAILY)        Notion DB
Google News RSS ────────┼─ Discovery + Classify ──────▶ Status: New
LinkedIn via Exa ───────┤  Claude Haiku
DeFi Llama raises ──────┘

Smart Money              run.py (WEEKLY)               Notion DB
Watchlist ──────────────▶ New follows detected ───────▶ Status: New
(followed_accounts.txt)   Deduplicate via SQLite        + Watcher data

                          score_run.py (WEEKLY)         Notion DB
Notion (Status=New) ─────▶ Phase 1: Hard filter ───────▶ Status: Filtered
                          Phase 2: Claude Haiku          Status: Scored
                          Thesis scoring                 + Score 0-100
                                                        + Initial Recommendation

                          enrich_funding.py (WEEKLY)    Notion DB
Notion (watch/deep_dive)  DeFi Llama + Surf ──────────▶ Funding fields
                          funding lookup                 updated

                          DISCORD AGENT (ON-DEMAND)     Notion DB
Discord command ─────────▶ Claude Opus                 ▶ Status: Deep_Dived
"Deep-dive @handle"        web_search + web_fetch        + Full memo
                          IC history retrieval

                          VOTING DASHBOARD (CONTINUOUS) Notion DB
Notion (Status=Scored) ──▶ Team votes ▲ ▼ ────────────▶ Vote counts
                          Partner assigns                + Voters
                          @iosg.vc auth (Google OAuth)   + Assigned_To


STORAGE
───────
┌──────────────────────────────────────────────────────────────────┐
│  NOTION DATABASE (source of truth, ~30 fields per project)       │
│  • Identity: name, X handle, profile link, account ID           │
│  • Profile: bio, tweet analysis, followers, verified status      │
│  • Classification: sector, stage, token status, one-liner        │
│  • Pipeline: status, score, recommendation, memo, scoring JSON   │
│  • Funding: raised, round date, amount, valuation, investors     │
│  • Voting: vote_up, vote_down, voters, assigned_to, reviewed     │
│  • IC tracking: IC_Decision, IC_Why, IC_Date                     │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  SQLITE (state.db — local)                           │
│  • known_accounts — every X account ever seen (deduplication)   │
│  • run_log — audit trail (date, watchlist size, new found)       │
│  • votes — team vote records (synced to Notion)                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  IC KNOWLEDGE BASE (local, gitignored)               │
│  • 69 IC meeting transcripts                                     │
│  • 46 fund research pieces                                       │
│  • Pre-indexed with Voyage AI → 13MB vector index               │
│  • Used by deep-dive agent for historical context                │
└──────────────────────────────────────────────────────────────────┘
```

---

## Weekly Workflow (Darko's Routine)

```
MONDAY
──────
$ python3 run_watchlist.py  ← Smart money: who are top investors/founders
                              following this week?
                              Output: new projects in Notion (Status=New)
                              + watcher signal

$ python3 run_score.py      ← Score everything in the New queue
                              Phase 1: drop noise (people, stale, L1/L2/Gaming/NFT)
                              Phase 2: AI scores 0-100 vs fund thesis
                              Output: projects in Notion (Status=Scored)

$ python3 enrich_funding.py ← Fill in funding data for top candidates
                              Checks DeFi Llama + Surf for raises
                              Output: Notion funding fields populated

THEN → Review Notion, check scores for deep_dives

DISCORD (on-demand)
────────────────────────────
"Deep-dive @projecthandle. Follow shared/prompts/deep_dive_manual.md
 for steps and shared/prompts/memo_format.md for the memo format.
 Never use Anthropic API — web_search and web_fetch only."

Agent runs ~5-10 min, posts memo back to Discord thread
→ Also writes memo to Notion

DAILY (automated)
──────────────────
$ python3 run_daily.py      ← Runs 5 discovery scripts in sequence
                              New projects added to Notion throughout the day
```

---

## Scale & Volume (Approximate)

| Metric | Volume |
|---|---|
| New projects discovered / day | 10–30 |
| Smart money new follows / week | 400–800 (after dedup) |
| Projects scored / week | 300–500 |
| Deep-dive recommendations / week | 50–150 |
| Memos produced (on-demand) | 50-150 |
| IC transcripts indexed | 69 |
| Research pieces indexed | 46 |
| Unique projects in Notion DB | Growing, ~1000s |
| Watchlist accounts | ~600 |
| SQLite known_accounts | Growing (dedup guard) |

---

## Investment Thesis (9 Active Themes)

The AI scoring is grounded in `shared/prompts/thesis_doc.md`, built from IC transcripts:

1. **Consumer apps** — Web2-grade crypto UX (Pump, Hyperliquid analogues)
2. **Stablecoin payment rails** — B2B cross-border, not P2P
3. **Hyperliquid-as-platform** — Mobile-first DeFi on HyperEVM
4. **RWA on-chain** — Credit/yield > tokenized equities
5. **Prediction markets** — Structural primitives only (Polymarket entrenched)
6. **Crypto card / DeFi neobank** — Winner-take-most-but-not-all
7. **Web2-encoded / mainstream pipeline** — Sweepstakes, creator coins
8. **Asia-edge** — Distribution + cap-table access
9. **AI x Crypto** — Agentic payments + DePIN compute

---
