# Deep-Dive Manual Instructions

## ⛔ HARD RULE — NO ANTHROPIC API
Never call the Anthropic API or any LLM API for research. All information must come from web_search and web_fetch only. No exceptions.

## Steps

**1.** `python3 scripts/get_project.py @{handle}` — grab `notion_id`, `username`, `one_liner`, `sectors`.

**2.** If purely Web2 (no crypto/blockchain) → short PASS memo, write to Notion, stop.

**3.** Research via web_search + web_fetch only:
- Team: real names, LinkedIn/GitHub, priors. Flag anon/rugs/rebrands.
- Funding: RootData, CryptoRank, Crunchbase, Messari — total raised, last round (stage/date/amount/lead). Not disclosed → null, never guess.
- Product: fetch site, verify contracts, GitHub <90d activity.
- Traction: TVL via DeFiLlama, users, volume, partnerships. Amounts/dates only.
- Sector comps: 3–6 direct/indirect competitors — latest round date, amount, lead investor.
- VC thesis angle: what macro shift made this sector viable now (2025–26)? One historical analogy.
- Red flags: anon custody, dead repo, ghost community, copycat, farmed engagement.
If dead/scam after 2 searches → short PASS memo, write to Notion, stop.

**4.** Write memo following shared/prompts/memo_format.md (structure) and shared/prompts/SKILL_en.md (writing style + IOSG context).

**5.** Write and run `/tmp/write_memo.py`:
```python
import sys; sys.path.insert(0, ".")
from shared.notion import (
    get_project, update_row,
    PROP_MEMO, PROP_STATUS, PROP_LAST_TOUCHED, PROP_RECOMMENDATION,
    PROP_RAISED, PROP_LAST_ROUND_DATE, PROP_LAST_ROUND_AMOUNT,
    PROP_LAST_ROUND_VALUATION, PROP_INVESTORS,
)
from datetime import datetime

notion_id = "<notion_id>"
existing = get_project(notion_id)

# PASS → "Pass", anything else (WATCH / TAKE_MEETING) → "Watch"
recommendation = "Pass"  # or "Watch"

fields = {
    PROP_MEMO:           """<memo>""",
    PROP_STATUS:         "Deep_Dived",
    PROP_LAST_TOUCHED:   datetime.today().strftime("%Y-%m-%d"),
    PROP_RECOMMENDATION: recommendation,
}

# Populate fundraising fields only if not already set
fields[PROP_RAISED] = <True/False>          # always set — True if any round exists
if not existing["last_round_date"]:
    pass  # fields[PROP_LAST_ROUND_DATE] = "YYYY-MM-DD"   # omit if not disclosed
if not existing["last_round_amount"]:
    pass  # fields[PROP_LAST_ROUND_AMOUNT] = "$Xm Seed/Series A"
if not existing["last_round_valuation"]:
    pass  # fields[PROP_LAST_ROUND_VALUATION] = "$XM"
if not existing["investors"]:
    pass  # fields[PROP_INVESTORS] = "Lead, Co-investor"

update_row(notion_id, fields)
print("Done")
```

Replace each `pass  #` line with the actual assignment when data is available; remove the line entirely when data is not disclosed.

**6.** Print `[ok] @handle → Deep_Dived` or `[error] @handle: reason`.

## Rules
- Source URL per claim
- Not disclosed > hallucinated
- Always end with at least one web_search + web_fetch
- **Never use Anthropic API or any LLM API for research**
