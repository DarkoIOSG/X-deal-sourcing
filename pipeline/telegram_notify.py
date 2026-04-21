import time
import requests
from datetime import datetime, timezone
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_MAX_CHARS = 4000


def _send(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=15)
    if not r.ok:
        print(f"  [telegram error] {r.status_code}: {r.text}")
    r.raise_for_status()


def _notion_page_url(page_id: str) -> str:
    clean = page_id.replace("-", "")
    return f"https://notion.so/{clean}"


def _format_date(value: str) -> str:
    if not value:
        return "unknown"
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%a %b %d %H:%M:%S %z %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def _is_recent(created_at: str, years: int = 2) -> bool:
    if not created_at:
        return False
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%a %b %d %H:%M:%S %z %Y"):
        try:
            dt = datetime.strptime(created_at.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).days / 365 <= years
        except ValueError:
            continue
    return False


def _build_entry(a: dict) -> str:
    profile_url = f"https://x.com/i/user/{a['id']}"
    notion_url = _notion_page_url(a["notion_page_id"]) if a.get("notion_page_id") else ""
    watchers = ", ".join(f"@{w}" for w in a.get("watchers", []))

    lines = [
        f"<b>{a.get('display_name') or a.get('username', '')}</b> (<a href='{profile_url}'>@{a.get('username', '')}</a>)",
        f"📅 {_format_date(a.get('created_at', ''))}  👥 {a.get('watcher_count', 0)} watcher(s): {watchers}",
    ]
    if a.get("tweet_analysis"):
        lines.append(f"📝 {a['tweet_analysis']}")
    if notion_url:
        lines.append(f"🔗 <a href='{notion_url}'>Notion</a>")
    return "\n".join(lines)


def notify_new_projects(accounts: list[dict]):
    projects = [
        a for a in accounts
        if a.get("account_type") == "project" and _is_recent(a.get("created_at", ""))
    ]

    if not projects:
        print("  No new projects to notify about.")
        return

    print(f"  Sending {len(projects)} project(s) to Telegram...")

    # Sort by watcher count descending
    projects.sort(key=lambda a: a.get("watcher_count", 0), reverse=True)

    header = f"🚀 <b>Deal Sourcing — {len(projects)} new project(s)</b>\n\n"
    separator = "\n\n" + "─" * 20 + "\n\n"

    # Build batches that fit within Telegram's 4096 char limit
    current_batch = header
    for i, a in enumerate(projects):
        entry = _build_entry(a)
        addition = (separator + entry) if i > 0 else entry
        if len(current_batch) + len(addition) > TELEGRAM_MAX_CHARS:
            try:
                _send(current_batch)
                time.sleep(1)
            except Exception as e:
                print(f"  [warn] Telegram batch failed: {e}")
            current_batch = entry
        else:
            current_batch += addition

    if current_batch:
        try:
            _send(current_batch)
        except Exception as e:
            print(f"  [warn] Telegram final batch failed: {e}")
