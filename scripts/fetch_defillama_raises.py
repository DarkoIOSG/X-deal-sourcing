"""
fetch_defillama_raises.py

Fetches crypto fundraising rounds from DeFiLlama Pro API (last N days),
resolves X handles via DeFiLlama protocol pages + Sorsa search fallback,
and pushes new entries to Notion with Status = "New" and funding data pre-filled.

Usage:
    python scripts/fetch_defillama_raises.py            # live run (last 30 days)
    python scripts/fetch_defillama_raises.py --dry-run  # skip Notion writes
    python scripts/fetch_defillama_raises.py --days 7   # last 7 days
    python scripts/fetch_defillama_raises.py --sample   # print raw API output and exit
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

sys.path.insert(0, ".")
from config import NOTION_TOKEN, NOTION_DATABASE_ID, EXA_API_KEY, DEFILLAMA_API_KEY
from api.sorsa import search_tweets, username_to_id, get_profiles_batch
from exa_py import Exa

_exa: Exa | None = None

def _get_exa() -> Exa:
    global _exa
    if _exa is None:
        _exa = Exa(EXA_API_KEY)
    return _exa

# Matches twitter.com/handle or x.com/handle — same pattern as search_thematic.py
_HANDLE_RE = re.compile(
    r'(?:twitter|x)\.com/'
    r'(?!share|intent|home|search|hashtag|status|i/|messages|explore|notifications|settings|'
    r'privacy|tos|about|help|download|login|signup|compose)'
    r'([A-Za-z0-9_]{1,50})',
    re.IGNORECASE,
)

def _extract_handle(text: str) -> str | None:
    for m in _HANDLE_RE.finditer(text):
        h = m.group(1).rstrip("/")
        if h.lower() not in ("status", "share", "intent"):
            return h
    return None

# ── Auth ──────────────────────────────────────────────────────────────────────
RAISES_URL = f"https://pro-api.llama.fi/{DEFILLAMA_API_KEY}/api/raises"

_NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# ── Mappings ──────────────────────────────────────────────────────────────────
CATEGORY_TO_SECTOR = {
    # DeFi
    "DeFi": "DeFi",
    "CeFi": "DeFi",
    "Stablecoin": "DeFi",
    "DEX": "DeFi",
    "Lending": "DeFi",
    "Yield": "DeFi",
    "Yield Aggregator": "DeFi",
    "Liquid Staking": "DeFi",
    "Exchange": "DeFi",
    "CEX": "DeFi",
    "DeFi & CeFi": "DeFi",
    # L1/L2
    "L1": "L1",
    "Layer 1": "L1",
    "L2": "L2",
    "Layer 2": "L2",
    "Base Layers & Scaling": "Infrastructure",
    # Infrastructure
    "Infrastructure": "Infrastructure",
    "Wallet": "Infrastructure",
    "Bridge": "Infrastructure",
    "Oracle": "Infrastructure",
    "Data": "Infrastructure",
    "Security": "Infrastructure",
    "Analytics": "Infrastructure",
    "Payments": "Infrastructure",
    # AI
    "AI": "AI",
    "AI, Analytics & Data": "AI",
    # Other
    "Gaming": "Gaming",
    "NFT": "NFT",
    "DAO": "DAO",
    "Social": "Social",
    "RWA": "RWA",
}

ROUND_TO_STAGE = {
    "Pre-Seed": "pre-seed",
    "Pre-seed": "pre-seed",
    "Angel": "pre-seed",
    "Angel Round": "pre-seed",
    "Seed": "seed",
    "Seed Round": "seed",
    "Private": "seed",
    "Private Round": "seed",
    "Series A": "growth",
    "Series B": "growth",
    "Series C": "growth",
    "Series D": "growth",
    "Strategic": "growth",
    "Strategic Round": "growth",
    "Growth": "growth",
    "Grant": "unknown",
}


def _map_sector(category: str, category_group: str) -> list[str]:
    for key in (category, category_group):
        if key in CATEGORY_TO_SECTOR:
            return [CATEGORY_TO_SECTOR[key]]
    return ["Other"]


def _map_stage(round_name: str) -> str:
    return ROUND_TO_STAGE.get(round_name, "unknown")


def _format_amount(amount, round_name: str) -> str:
    if amount is None:
        return round_name or "Unknown"
    try:
        amt = float(amount)
        label = f"${amt / 1000:.1f}B" if amt >= 1000 else f"${amt:.1f}M"
        return f"{label} {round_name}".strip()
    except (TypeError, ValueError):
        return f"${amount}M {round_name}".strip()


# ── DeFiLlama ─────────────────────────────────────────────────────────────────

def fetch_raises() -> list[dict]:
    r = requests.get(RAISES_URL, timeout=30)
    r.raise_for_status()
    return r.json().get("raises", [])


def get_protocol_twitter(defillama_id: str) -> str | None:
    if not defillama_id:
        return None
    slug = defillama_id.replace("parent#", "").strip()
    try:
        r = requests.get(f"https://api.llama.fi/protocol/{slug}", timeout=10)
        if r.ok:
            data = r.json()
            handle = data.get("twitter") or data.get("twitterHandle")
            if handle:
                return handle.lstrip("@").strip()
    except Exception:
        pass
    return None


# ── X handle resolution ───────────────────────────────────────────────────────

def _exa_find_handle(name: str) -> str | None:
    """Search Exa for the project's company page and extract its X handle."""
    try:
        res = _get_exa().search(
            f"{name} crypto official",
            type="auto",
            category="company",
            num_results=5,
            contents={"text": {"max_characters": 2000}},
        )
        for r in res.results:
            text = (getattr(r, "text", "") or "") + " " + r.url
            h = _extract_handle(text)
            if h:
                return h
    except Exception:
        pass
    return None


def resolve_x_handle(name: str, defillama_id: str) -> str | None:
    # 1. DeFiLlama protocol page (structured, most reliable)
    handle = get_protocol_twitter(defillama_id)
    if handle:
        return handle

    # 2. Exa web search — finds company sites that link to their X profile
    handle = _exa_find_handle(name)
    if handle:
        return handle

    # 3. Sorsa tweet search — look for the project's own account in tweet authors
    try:
        tweets = search_tweets(f'"{name}" crypto', order="popular", max_results=30)
        name_key = name.lower().replace(" ", "")
        for tweet in tweets:
            author = tweet.get("author", {})
            username = (author.get("username") or "").lower()
            display = (author.get("name") or "").lower().replace(" ", "")
            if name_key in username or name_key in display:
                return author.get("username")
    except Exception:
        pass

    return None


# ── Notion serialisers (inline to avoid import side-effects) ──────────────────

def _text(v):   return {"rich_text": [{"text": {"content": str(v or "")[:2000]}}]}
def _title(v):  return {"title": [{"text": {"content": str(v or "")[:2000]}}]}
def _number(v): return {"number": v if isinstance(v, (int, float)) else None}
def _checkbox(v): return {"checkbox": bool(v)}
def _url(v):    return {"url": str(v) if v else None}
def _select(v): return {"select": {"name": v} if v else None}
def _multi_select(vals): return {"multi_select": [{"name": v} for v in vals if v]}
def _date(v):
    if not v:
        return {"date": None}
    if isinstance(v, datetime):
        return {"date": {"start": v.strftime("%Y-%m-%d")}}
    return {"date": {"start": str(v)}}


# ── Notion helpers ────────────────────────────────────────────────────────────

def name_exists(name: str) -> bool:
    payload = {
        "filter": {"property": "Name", "title": {"equals": name}},
        "page_size": 1,
    }
    r = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query",
        headers=_NOTION_HEADERS,
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return len(r.json().get("results", [])) > 0


def push_to_notion(raise_: dict, handle: str | None, profile: dict | None) -> str:
    raise_date = datetime.fromtimestamp(raise_["date"], tz=timezone.utc)
    amount_str = _format_amount(raise_.get("amount"), raise_.get("round", ""))
    investors = ", ".join(
        (raise_.get("leadInvestors") or []) + (raise_.get("otherInvestors") or [])
    )
    x_url = None
    if handle:
        uid = profile.get("id") if profile else None
        x_url = f"https://x.com/i/user/{uid}" if uid else f"https://x.com/{handle}"

    properties = {
        "Name":               _title(raise_["name"]),
        "Username":           _text(handle or ""),
        "X Profile":          _url(x_url),
        "Official Bio":       _text(raise_.get("sector", "")),
        "One-liner":          _text(f"{amount_str} · {', '.join(raise_.get('chains', []))}"),
        "Account Type":       _select("project"),
        "Sector":             _multi_select(_map_sector(raise_.get("category", ""), raise_.get("categoryGroup", ""))),
        "Stage":              _select(_map_stage(raise_.get("round", ""))),
        "Token Status":       _select("unknown"),
        "Status":             _select("New"),
        "Raised":             _checkbox(True),
        "Checked Fundraising": _checkbox(True),
        "Last Round Date":    _date(raise_date),
        "Last Round Amount":  _text(amount_str),
        "Last Round Valuation": _text(str(raise_["valuation"]) if raise_.get("valuation") else ""),
        "Investors":          _text(investors),
    }

    if profile:
        properties["Account ID"] = _number(int(profile["id"]) if profile.get("id") else None)
        properties["Followers Count"] = _number(profile.get("followers_count"))
        properties["Friends Count"] = _number(profile.get("followings_count"))
        properties["Tweets Count"] = _number(profile.get("tweets_count"))
        properties["Verified"] = _checkbox(profile.get("verified", False))

    payload = {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties}
    r = requests.post("https://api.notion.com/v1/pages", headers=_NOTION_HEADERS, json=payload, timeout=30)
    if not r.ok:
        print(f"  [notion error] {r.status_code}: {r.text}")
    r.raise_for_status()
    return r.json()["id"]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync DeFiLlama raises → Notion")
    parser.add_argument("--dry-run", action="store_true", help="Skip Notion writes")
    parser.add_argument("--days", type=int, default=30, help="Look-back window in days")
    parser.add_argument("--sample", action="store_true", help="Print raw API output and exit")
    args = parser.parse_args()

    print("Fetching raises from DeFiLlama Pro API…")
    all_raises = fetch_raises()
    print(f"Total raises in dataset: {len(all_raises)}")

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=args.days)
    recent = [
        r for r in all_raises
        if datetime.fromtimestamp(r["date"], tz=timezone.utc) >= cutoff
    ]
    print(f"Raises in last {args.days} days: {len(recent)}")

    if args.sample:
        print(f"\n--- Raw DeFiLlama output (first 3 raises) ---\n")
        print(json.dumps(recent[:3], indent=2))
        return

    pushed, skipped, failed = 0, 0, 0

    for raise_ in recent:
        name = raise_["name"]
        date_str = datetime.fromtimestamp(raise_["date"], tz=timezone.utc).strftime("%Y-%m-%d")
        amount_str = _format_amount(raise_.get("amount"), raise_.get("round", "?"))
        print(f"\n→ {name}  |  {amount_str}  |  {date_str}")

        if name_exists(name):
            print(f"  skip — already in Notion")
            skipped += 1
            continue

        handle = resolve_x_handle(name, raise_.get("defillamaId", ""))
        print(f"  X: @{handle}" if handle else "  X: not found (DeFiLlama + Exa + Sorsa)")

        profile = None
        if handle:
            try:
                uid = username_to_id(handle)
                profiles = get_profiles_batch([uid])
                profile = profiles[0] if profiles else None
            except Exception as e:
                print(f"  [sorsa] {e}")

        if args.dry_run:
            investors = ", ".join(
                (raise_.get("leadInvestors") or []) + (raise_.get("otherInvestors") or [])
            )
            print(f"  [dry-run] sector={raise_.get('category')}  investors={investors or '—'}")
            pushed += 1
            continue

        try:
            page_id = push_to_notion(raise_, handle, profile)
            print(f"  ✓ Notion page created → {page_id[:8]}…")
            pushed += 1
        except Exception as e:
            print(f"  [error] {e}")
            failed += 1

        time.sleep(0.3)

    print(f"\n--- Done: {pushed} pushed  {skipped} skipped  {failed} failed ---")


if __name__ == "__main__":
    main()
