"""
High-level Notion wrapper for the deal-sourcing pipeline.

All Notion property names live here as constants — change one line when you
rename a column in the UI instead of hunting through every script.
"""
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from config import NOTION_TOKEN, NOTION_DATABASE_ID

load_dotenv()

# ── Property name constants ───────────────────────────────────────────────────
# Identifiers
PROP_NAME           = "Name"
PROP_USERNAME       = "Username"
PROP_ACCOUNT_ID     = "Account ID"
PROP_X_PROFILE      = "X Profile"

# Profile data
PROP_BIO            = "Official Bio"
PROP_TWEET_ANALYSIS = "Tweet Analysis"
PROP_ONE_LINER      = "One-liner"
PROP_ENTITIES       = "Entities"
PROP_FOLLOWERS      = "Followers Count"
PROP_FRIENDS        = "Friends Count"
PROP_TWEETS_COUNT   = "Tweets Count"
PROP_VERIFIED       = "Verified"
PROP_ACCOUNT_CREATED = "Account Created"
PROP_LAST_TWEET     = "Last Tweet Date"
PROP_WATCHER_COUNT  = "Watcher Count"
PROP_WATCHERS       = "Watchers"

# Classification
PROP_ACCOUNT_TYPE   = "Account Type"
PROP_SECTOR         = "Sector"
PROP_TOKEN_STATUS   = "Token Status"
PROP_STAGE          = "Stage"

# Pipeline state
PROP_STATUS         = "Status"
PROP_SCORE          = "Score"
PROP_RECOMMENDATION = "Recommendation"
PROP_SCORING_JSON   = "Scoring_JSON"
PROP_MEMO           = "Memo"
PROP_PROCESSED_AT   = "Processed_At"
PROP_FILTERED_REASON = "Filtered_Reason"
PROP_LAST_TOUCHED   = "Notion_Last_Touched"

# Funding data (populated during deep dive / Surf enrichment)
PROP_CHECKED_ON_SURF       = "Checked Fundraising"
PROP_RAISED                = "Raised"
PROP_LAST_ROUND_DATE       = "Last Round Date"
PROP_LAST_ROUND_AMOUNT     = "Last Round Amount"
PROP_LAST_ROUND_VALUATION  = "Last Round Valuation"
PROP_INVESTORS             = "Investors"

# Stage classification (populated during deep dive)
PROP_STAGE_EARLY_GROWTH = "Stage_Early_Growth"

# Audit flag (populated by audit_early_passed.py)
PROP_AUDIT_FLAG = "Audit_Flag"

# IC feedback (manual)
PROP_IC_DECISION    = "IC_Decision"
PROP_IC_WHY         = "IC_Why"
PROP_IC_DATE        = "IC_Date"

# Team voting (written by webapp)
PROP_VOTE_UP        = "Vote_Up"
PROP_VOTE_DOWN      = "Vote_Down"
PROP_VOTERS         = "Voters"
PROP_VOTE_REVIEWED  = "Vote_Reviewed"

# ── Property type map (used by update_row) ────────────────────────────────────
_FIELD_TYPES: dict[str, str] = {
    PROP_NAME:           "title",
    PROP_USERNAME:       "rich_text",
    PROP_BIO:            "rich_text",
    PROP_TWEET_ANALYSIS: "rich_text",
    PROP_ONE_LINER:      "rich_text",
    PROP_ENTITIES:       "rich_text",
    PROP_WATCHERS:       "rich_text",
    PROP_SCORING_JSON:   "rich_text",
    PROP_MEMO:           "rich_text",
    PROP_FILTERED_REASON:"rich_text",
    PROP_IC_WHY:         "rich_text",
    PROP_ACCOUNT_ID:     "number",
    PROP_FOLLOWERS:      "number",
    PROP_FRIENDS:        "number",
    PROP_TWEETS_COUNT:   "number",
    PROP_SCORE:          "number",
    PROP_WATCHER_COUNT:  "number",
    PROP_VERIFIED:       "checkbox",
    PROP_X_PROFILE:      "url",
    PROP_ACCOUNT_CREATED:"date",
    PROP_LAST_TWEET:     "date",
    PROP_PROCESSED_AT:   "date",
    PROP_IC_DATE:        "date",
    PROP_LAST_TOUCHED:   "date",
    PROP_STATUS:         "select",
    PROP_RECOMMENDATION: "select",
    PROP_ACCOUNT_TYPE:   "select",
    PROP_TOKEN_STATUS:   "select",
    PROP_STAGE:               "select",
    PROP_STAGE_EARLY_GROWTH:  "select",
    PROP_AUDIT_FLAG:          "select",
    PROP_IC_DECISION:         "select",
    PROP_SECTOR:         "multi_select",
    PROP_VOTE_UP:               "number",
    PROP_VOTE_DOWN:             "number",
    PROP_VOTERS:                "rich_text",
    PROP_VOTE_REVIEWED:         "checkbox",
    PROP_CHECKED_ON_SURF:       "checkbox",
    PROP_RAISED:                "checkbox",
    PROP_LAST_ROUND_DATE:       "date",
    PROP_LAST_ROUND_AMOUNT:     "rich_text",
    PROP_LAST_ROUND_VALUATION:  "rich_text",
    PROP_INVESTORS:             "rich_text",
}

_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}
_DB_URL = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
_PAGE_URL = "https://api.notion.com/v1/pages"


# ── Property serialisers ──────────────────────────────────────────────────────

def _serialise(prop_name: str, value) -> dict:
    ptype = _FIELD_TYPES.get(prop_name, "rich_text")
    if ptype == "title":
        return {"title": [{"text": {"content": str(value or "")[:2000]}}]}
    if ptype == "rich_text":
        text = str(value or "")
        chunks = [text[i:i+1990] for i in range(0, max(len(text), 1), 1990)]
        return {"rich_text": [{"text": {"content": chunk}} for chunk in chunks[:100]]}
    if ptype == "number":
        return {"number": value if isinstance(value, (int, float)) else None}
    if ptype == "checkbox":
        return {"checkbox": bool(value)}
    if ptype == "url":
        return {"url": str(value) if value else None}
    if ptype == "select":
        return {"select": {"name": value} if value else None}
    if ptype == "multi_select":
        items = value if isinstance(value, list) else [value]
        return {"multi_select": [{"name": v} for v in items if v]}
    if ptype == "date":
        parsed = _parse_date(str(value)) if value else None
        return {"date": {"start": parsed} if parsed else None}
    return {"rich_text": [{"text": {"content": str(value or "")[:2000]}}]}


def _parse_date(value: str) -> str | None:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%a %b %d %H:%M:%S %z %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ── Property readers ──────────────────────────────────────────────────────────

def _read(props: dict, name: str):
    prop = props.get(name) or {}
    ptype = _FIELD_TYPES.get(name, "rich_text")
    if ptype == "title":
        t = prop.get("title", [])
        return t[0]["plain_text"] if t else ""
    if ptype == "rich_text":
        rt = prop.get("rich_text", [])
        return rt[0]["plain_text"] if rt else ""
    if ptype == "number":
        return prop.get("number")
    if ptype == "checkbox":
        return prop.get("checkbox", False)
    if ptype == "url":
        return prop.get("url")
    if ptype == "select":
        s = prop.get("select")
        return s["name"] if s else ""
    if ptype == "multi_select":
        return [item["name"] for item in prop.get("multi_select", [])]
    if ptype == "date":
        d = prop.get("date")
        return d["start"] if d else ""
    return ""


def _parse_page(page: dict) -> dict:
    props = page["properties"]
    raw_id = _read(props, PROP_ACCOUNT_ID)
    score_json_raw = _read(props, PROP_SCORING_JSON)
    try:
        score_json = json.loads(score_json_raw) if score_json_raw else {}
    except json.JSONDecodeError:
        score_json = {}
    voters_raw = _read(props, PROP_VOTERS)
    try:
        voters = json.loads(voters_raw) if voters_raw else {}
    except (json.JSONDecodeError, ValueError):
        voters = {}
    return {
        "notion_id":      page["id"],
        "account_id":     str(int(float(raw_id))) if raw_id else "",
        "name":           _read(props, PROP_NAME),
        "username":       _read(props, PROP_USERNAME),
        "bio":            _read(props, PROP_BIO),
        "tweet_analysis": _read(props, PROP_TWEET_ANALYSIS),
        "one_liner":      _read(props, PROP_ONE_LINER),
        "sectors":        _read(props, PROP_SECTOR),
        "stage":          _read(props, PROP_STAGE),
        "token_status":   _read(props, PROP_TOKEN_STATUS),
        "account_type":   _read(props, PROP_ACCOUNT_TYPE),
        "last_tweet":     _read(props, PROP_LAST_TWEET),
        "status":               _read(props, PROP_STATUS),
        "score":                _read(props, PROP_SCORE),
        "recommendation":       _read(props, PROP_RECOMMENDATION),
        "scoring_json":         score_json,
        "memo":                 _read(props, PROP_MEMO),
        "ic_decision":          _read(props, PROP_IC_DECISION),
        "raised":               _read(props, PROP_RAISED),
        "last_round_date":      _read(props, PROP_LAST_ROUND_DATE),
        "last_round_amount":    _read(props, PROP_LAST_ROUND_AMOUNT),
        "last_round_valuation": _read(props, PROP_LAST_ROUND_VALUATION),
        "investors":            _read(props, PROP_INVESTORS),
        "watcher_count":        _read(props, PROP_WATCHER_COUNT),
        "watchers":             _read(props, PROP_WATCHERS),
        "x_profile":            _read(props, PROP_X_PROFILE),
        "processed_at":         _read(props, PROP_PROCESSED_AT),
        "vote_reviewed":        _read(props, PROP_VOTE_REVIEWED),
        "vote_up":              _read(props, PROP_VOTE_UP) or 0,
        "vote_down":            _read(props, PROP_VOTE_DOWN) or 0,
        "voters":               voters,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def query_candidates(status: str = "Scored",
                     recommendation: str = "deep_dive") -> list[dict]:
    """Return all pages matching status + recommendation, sorted by Score desc."""
    payload = {
        "filter": {
            "and": [
                {"property": PROP_STATUS,         "select": {"equals": status}},
                {"property": PROP_RECOMMENDATION, "select": {"equals": recommendation}},
            ]
        },
        "sorts": [{"property": PROP_SCORE, "direction": "descending"}],
    }
    pages: list[dict] = []
    cursor = None
    while True:
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(_DB_URL, headers=_HEADERS, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        pages.extend(_parse_page(p) for p in data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return pages


def query_voting_projects() -> list[dict]:
    """Return all Scored watch/deep_dive projects for the voting webapp (one query)."""
    payload = {
        "filter": {
            "and": [
                {"property": PROP_STATUS, "select": {"equals": "Deep_Dived"}},
                {"property": PROP_RECOMMENDATION, "select": {"equals": "watch"}},
                {"property": PROP_VOTE_REVIEWED, "checkbox": {"equals": False}},
            ]
        },
        "sorts": [{"property": PROP_SCORE, "direction": "descending"}],
    }
    pages: list[dict] = []
    cursor = None
    while True:
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(_DB_URL, headers=_HEADERS, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        pages.extend(_parse_page(p) for p in data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return pages


def flag_reviewed(notion_id: str):
    """Mark a project as reviewed (voting cycle complete)."""
    update_row(notion_id, {PROP_VOTE_REVIEWED: True})


def sync_votes(notion_id: str, up: int, down: int, voters: dict):
    """Write aggregate vote counts back to a Notion page."""
    import json
    update_row(notion_id, {
        PROP_VOTE_UP:   up,
        PROP_VOTE_DOWN: down,
        PROP_VOTERS:    json.dumps(voters, ensure_ascii=False),
    })


def get_project(notion_id: str) -> dict:
    """Fetch a single project's full data by Notion page ID."""
    r = requests.get(f"{_PAGE_URL}/{notion_id}", headers=_HEADERS, timeout=30)
    r.raise_for_status()
    return _parse_page(r.json())


def update_row(notion_id: str, fields: dict):
    """
    Write arbitrary fields back to a Notion page.
    Keys are property name constants from this file, values are plain Python types.

    Example:
        update_row(notion_id, {
            PROP_MEMO:          "Deep-dive memo text...",
            PROP_STATUS:        "Deep_Dived",
            PROP_LAST_TOUCHED:  "2026-05-08",
        })
    """
    properties = {name: _serialise(name, value) for name, value in fields.items()}
    r = requests.patch(
        f"{_PAGE_URL}/{notion_id}",
        headers=_HEADERS,
        json={"properties": properties},
        timeout=30,
    )
    if not r.ok:
        print(f"  [notion error] {r.status_code}: {r.text}")
    r.raise_for_status()
