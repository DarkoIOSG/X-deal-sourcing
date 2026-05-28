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
from shared.notion import update_row, PROP_MEMO, PROP_STATUS, PROP_LAST_TOUCHED, PROP_RAISED, PROP_LAST_ROUND_DATE, PROP_LAST_ROUND_AMOUNT, PROP_INVESTORS
from datetime import datetime
update_row("<notion_id>", {
    PROP_MEMO: """<memo>""",
    PROP_STATUS: "Deep_Dived",
    PROP_LAST_TOUCHED: datetime.today().strftime("%Y-%m-%d"),
    PROP_RAISED: <True/False/None>,
    # PROP_LAST_ROUND_DATE: "YYYY-MM-DD",
    # PROP_LAST_ROUND_AMOUNT: "$Xm Seed/Series A",
    # PROP_INVESTORS: "Lead, Co-investor",
})
print("Done")
```

**6.** Print `[ok] @handle → Deep_Dived` or `[error] @handle: reason`.

## Rules
- Source URL per claim
- Not disclosed > hallucinated
- Always end with at least one web_search + web_fetch
- **Never use Anthropic API or any LLM API for research**
