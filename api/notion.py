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
        "Account ID": _text(account["id"]),
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
