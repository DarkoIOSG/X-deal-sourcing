import json
import requests
from datetime import datetime
from config import NOTION_TOKEN, NOTION_DATABASE_ID

_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def _text(value: str) -> dict:
    return {"rich_text": [{"text": {"content": str(value or "")[:2000]}}]}


def _title(value: str) -> dict:
    return {"title": [{"text": {"content": str(value or "")[:2000]}}]}


def _number(value) -> dict:
    return {"number": value if isinstance(value, (int, float)) else None}


def _checkbox(value: bool) -> dict:
    return {"checkbox": bool(value)}


def _url(value: str) -> dict:
    return {"url": str(value) if value else None}


def _select(value: str) -> dict:
    return {"select": {"name": value} if value else None}


def _multi_select(values: list[str]) -> dict:
    return {"multi_select": [{"name": v} for v in values if v]}


def _parse_date(value: str) -> str | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%a %b %d %H:%M:%S %z %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _date(value: str) -> dict:
    parsed = _parse_date(value)
    return {"date": {"start": parsed} if parsed else None}


def create_page(account: dict) -> str:
    profile_url = f"https://x.com/i/user/{account['id']}"
    watchers_str = ", ".join(account.get("watchers", []))
    entities_str = "\n".join(account.get("entities", []))

    properties = {
        "Name": _title(account.get("display_name") or account.get("username", "")),
        "X Profile": _url(profile_url),
        "Account ID": _number(int(account["id"]) if account.get("id") else None),
        "Username": _text(account.get("username", "")),
        "Account Created": _date(account.get("created_at", "")),
        "Watcher Count": _number(account.get("watcher_count")),
        "Watchers": _text(watchers_str),
        "Official Bio": _text(account.get("description", "")),
        "Tweet Analysis": _text(account.get("tweet_analysis", "")),
        "Entities": _text(entities_str),
        "Followers Count": _number(account.get("followers_count")),
        "Friends Count": _number(account.get("followings_count")),
        "Tweets Count": _number(account.get("tweets_count")),
        "Last Tweet Date": _date(account.get("last_tweet_date", "")),
        "Verified": _checkbox(account.get("verified", False)),
        "Account Type": _select(account.get("account_type", "unknown")),
        "One-liner": _text(account.get("one_liner", "")),
        "Sector": _multi_select(account.get("sector", [])),
        "Token Status": _select(account.get("token_status", "unknown")),
        "Stage": _select(account.get("stage", "unknown")),
        "Status": _select("New"),
    }

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
    }

    r = requests.post("https://api.notion.com/v1/pages", headers=_HEADERS, json=payload, timeout=30)
    if not r.ok:
        print(f"\n  [notion error] {r.status_code}: {r.text}")
    r.raise_for_status()
    return r.json()["id"]


def update_page(page_id: str, account: dict):
    properties = {
        "Account Type": _select(account.get("account_type", "unknown")),
        "Tweet Analysis": _text(account.get("description", "")),
        "One-liner": _text(account.get("one_liner", "")),
        "Sector": _multi_select(account.get("sector", [])),
        "Token Status": _select(account.get("token_status", "unknown")),
        "Stage": _select(account.get("stage", "unknown")),
    }
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=_HEADERS,
        json={"properties": properties},
        timeout=30,
    )
    if not r.ok:
        print(f"\n  [notion error] {r.status_code}: {r.text}")
    r.raise_for_status()


# ── property readers (for query responses) ────────────────────────────────────

def _read_text(prop: dict) -> str:
    rt = (prop or {}).get("rich_text", [])
    return rt[0]["plain_text"] if rt else ""


def _read_title(prop: dict) -> str:
    t = (prop or {}).get("title", [])
    return t[0]["plain_text"] if t else ""


def _read_select(prop: dict) -> str:
    s = (prop or {}).get("select")
    return s["name"] if s else ""


def _read_multi_select(prop: dict) -> list[str]:
    return [item["name"] for item in (prop or {}).get("multi_select", [])]


def _read_number(prop: dict):
    return (prop or {}).get("number")


def _read_date(prop: dict) -> str:
    d = (prop or {}).get("date")
    return d["start"] if d else ""


def _parse_page(page: dict) -> dict:
    props = page.get("properties", {})
    raw_id = _read_number(props.get("Account ID"))
    account_id = str(int(float(raw_id))) if raw_id is not None else ""
    return {
        "page_id":        page["id"],
        "account_id":     account_id,
        "username":       _read_text(props.get("Username")),
        "display_name":   _read_title(props.get("Name")),
        "description":    _read_text(props.get("Tweet Analysis")),
        "one_liner":      _read_text(props.get("One-liner")),
        "sectors":        _read_multi_select(props.get("Sector")),
        "account_type":   _read_select(props.get("Account Type")),
        "last_tweet_date": _read_date(props.get("Last Tweet Date")),
        "status":         _read_select(props.get("Status")),
    }


# ── query & scoring ───────────────────────────────────────────────────────────

def query_new_accounts() -> list[dict]:
    """Return all pages with Status = New or Status empty (not yet processed)."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    base_filter = {
        "filter": {
            "and": [
                {
                    "or": [
                        {"property": "Status", "select": {"equals": "New"}},
                        {"property": "Status", "select": {"is_empty": True}},
                    ]
                },
                {"property": "Status", "select": {"does_not_equal": "Filtered"}},
                {"property": "Status", "select": {"does_not_equal": "Scored"}},
            ]
        }
    }

    pages: list[dict] = []
    cursor = None
    while True:
        payload = dict(base_filter)
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(url, headers=_HEADERS, json=payload, timeout=30)
        if not r.ok:
            print(f"\n  [notion error] {r.status_code}: {r.text}")
        r.raise_for_status()
        data = r.json()
        pages.extend(_parse_page(p) for p in data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    return pages


def update_scoring(page_id: str, result: dict):
    """Write Phase 2 scoring output back to the Notion page."""
    properties = {
        "Status":          _select("Scored"),
        "Score":           _number(result.get("thesis_fit_score")),
        "Recommendation":  _select(result.get("recommendation", "pass")),
        "Scoring_JSON":    _text(json.dumps(result)),
        "Processed_At":    _date(datetime.today().strftime("%Y-%m-%d")),
    }
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=_HEADERS,
        json={"properties": properties},
        timeout=30,
    )
    if not r.ok:
        print(f"\n  [notion error] {r.status_code}: {r.text}")
    r.raise_for_status()


def update_filtered(page_id: str, reason: str):
    """Mark a Phase 1 dropped project so it is skipped on future runs."""
    properties = {
        "Status":          _select("Filtered"),
        "Filtered_Reason": _text(reason),
        "Processed_At":    _date(datetime.today().strftime("%Y-%m-%d")),
    }
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=_HEADERS,
        json={"properties": properties},
        timeout=30,
    )
    if not r.ok:
        print(f"\n  [notion error] {r.status_code}: {r.text}")
    r.raise_for_status()
