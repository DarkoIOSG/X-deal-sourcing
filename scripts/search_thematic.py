"""
Thematic deal-sourcing — AI Derivative, FX, Crypto Infra for Fintech.

Signal sources per theme:
  1. Exa neural search on seed URLs (companies like the examples you gave)
  2. Exa keyword company search
  3. X tweet search via Sorsa (author IDs extracted directly)
  4. YC Algolia API — filtered by recent batches + per-theme tags

Pre-sync filter: only projects, no token yet, ≥200 followers.
Theme label is added to the Sector multi-select in Notion for filtering.

Run:
  python3 scripts/search_thematic.py
  python3 scripts/search_thematic.py --theme fx          # single theme
  python3 scripts/search_thematic.py --dry-run           # print candidates, skip Notion
"""

import re
import sys
import time
import argparse
import requests as _requests
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from exa_py import Exa
from config import EXA_API_KEY
from api.sorsa import username_to_id, search_tweets
from pipeline.enrich import enrich_profiles, enrich_tweets
from pipeline.analyze import analyze_accounts
from pipeline.notion_sync import sync_to_notion
from state import init_db, get_known_ids

# ── constants ─────────────────────────────────────────────────────────────────

MIN_FOLLOWERS = 200  # pre-sync filter: skip low-signal accounts

# Update when new YC batches are announced
YC_RECENT_BATCHES = ["Winter 2026", "Summer 2025", "Winter 2025", "Summer 2024"]

YC_ALGOLIA_APP_ID = "45BWZJ1SGC"
YC_ALGOLIA_INDEX  = "YCCompany_production"

# ── theme config ──────────────────────────────────────────────────────────────

THEMES: dict[str, dict] = {
    "ai_derivative": {
        "label": "AI Derivative",
        "seed_urls": [
            "https://www.silicondata.com/",
            "https://dashboard.ornnai.com/",
        ],
        "exa_queries": [
            "AI data infrastructure platform for financial markets startup",
            "AI derivatives analytics data platform early stage startup",
            "alternative data AI startup for hedge funds and trading",
        ],
        "x_queries": [
            '"AI data" (infrastructure OR platform) (fintech OR trading OR finance) -filter:retweets lang:en',
            '"AI derivative" OR "AI data layer" startup -filter:retweets lang:en',
        ],
        # YC tags to filter — OR logic within the list
        "yc_tags": ["Fintech", "Artificial Intelligence", "Data Engineering"],
    },
    "fx": {
        "label": "FX",
        "seed_urls": [
            "https://www.rectangle.fi/",
        ],
        "exa_queries": [
            "FX startup foreign exchange API B2B cross-border payments infrastructure",
            "foreign exchange fintech startup treasury FX management early stage",
            "embedded FX cross-border payments API startup",
        ],
        "x_queries": [
            '(FX OR "foreign exchange") (startup OR API OR infrastructure) fintech -filter:retweets lang:en',
            '"cross-border payments" FX treasury startup -filter:retweets lang:en',
        ],
        "yc_tags": ["Fintech", "Payments"],
    },
    "crypto_infra_fintech": {
        "label": "Crypto Infra Fintech",
        "seed_urls": [
            "https://yield.xyz",
            "https://checker.finance",
            "https://www.groundtech.co/",
        ],
        "exa_queries": [
            "crypto yield infrastructure fintech protocol onchain startup early stage",
            "onchain fintech crypto infrastructure DeFi startup",
            "crypto fintech rails infrastructure startup B2B",
        ],
        "x_queries": [
            '(crypto OR onchain OR DeFi) (infrastructure OR rails OR yield) fintech startup -filter:retweets lang:en',
            '"crypto infrastructure" OR "onchain fintech" startup -filter:retweets lang:en',
        ],
        "yc_tags": ["Fintech", "Crypto / Web3"],
    },
}

# ── Exa setup ─────────────────────────────────────────────────────────────────

_exa: Exa | None = None


def _get_exa() -> Exa:
    global _exa
    if _exa is None:
        _exa = Exa(api_key=EXA_API_KEY)
    return _exa


# Matches twitter.com/handle or x.com/handle, skips non-profile paths
_HANDLE_RE = re.compile(
    r'(?:twitter|x)\.com/'
    r'(?!share|intent|home|search|hashtag|status|i/|messages|explore|notifications|settings|'
    r'privacy|tos|about|help|download|login|signup|compose)'
    r'([A-Za-z0-9_]{1,50})',
    re.IGNORECASE,
)


def _extract_handle(text: str) -> str | None:
    """Return the first Twitter/X profile handle found in text or a URL string."""
    for m in _HANDLE_RE.finditer(text):
        h = m.group(1).rstrip("/")
        if h.lower() not in ("status", "share", "intent"):
            return h
    return None


# ── Exa helpers ───────────────────────────────────────────────────────────────

def _exa_similar(seed_url: str, n: int = 10) -> list[tuple[str, str]]:
    """
    Returns (url, handle_or_empty) pairs for pages similar to seed_url.
    Neural search on the URL — recommended replacement for deprecated find_similar().
    """
    try:
        res = _get_exa().search(
            seed_url,
            type="neural",
            num_results=n,
            contents={"text": {"max_characters": 2000}},
        )
        out = []
        for r in res.results:
            text = (getattr(r, "text", "") or "") + " " + r.url
            h = _extract_handle(text)
            out.append((r.url, h or ""))
        return out
    except Exception as e:
        print(f"    [exa] similar({seed_url}): {e}")
        return []


def _exa_company_search(query: str, n: int = 15) -> list[tuple[str, str]]:
    """Company search — returns (url, handle_or_empty) pairs."""
    try:
        res = _get_exa().search(
            query,
            type="auto",
            category="company",
            num_results=n,
            contents={"text": {"max_characters": 2000}},
        )
        out = []
        for r in res.results:
            text = (getattr(r, "text", "") or "") + " " + r.url
            h = _extract_handle(text)
            out.append((r.url, h or ""))
        return out
    except Exception as e:
        print(f"    [exa] company_search({query!r}): {e}")
        return []


def _resolve_website_to_handle(url: str) -> str | None:
    """Fetch a company website via Exa and extract its Twitter/X handle."""
    try:
        res = _get_exa().get_contents([url], text={"max_characters": 3000})
        if res.results:
            text = (getattr(res.results[0], "text", "") or "") + " " + url
            return _extract_handle(text)
    except Exception as e:
        print(f"    [exa] get_contents({url}): {e}")
    return None


# ── YC Algolia API ────────────────────────────────────────────────────────────

_yc_api_key: str | None = None


def _fetch_yc_api_key() -> str:
    """
    Extract YC's public Algolia search key from the companies page HTML.
    The key is injected at runtime as window.AlgoliaOpts and rotates occasionally,
    so we always fetch fresh rather than hardcoding.
    """
    global _yc_api_key
    if _yc_api_key:
        return _yc_api_key
    r = _requests.get(
        "https://www.ycombinator.com/companies",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    r.raise_for_status()
    m = re.search(r'AlgoliaOpts\s*=\s*\{"app":"[^"]+","key":"([^"]+)"\}', r.text)
    if not m:
        raise RuntimeError("Could not extract YC Algolia key from page — check AlgoliaOpts pattern")
    _yc_api_key = m.group(1)
    return _yc_api_key


def _yc_algolia_search(tags: list[str], batches: list[str] = YC_RECENT_BATCHES,
                       hits_per_page: int = 50) -> list[str]:
    """
    Query YC's Algolia index and return website URLs for matching companies.

    tags    — OR logic: returns companies that have ANY of these tags
    batches — OR logic: restricted to these batch names (e.g. "Winter 2025")
    """
    try:
        api_key = _fetch_yc_api_key()
    except Exception as e:
        print(f"    [yc] could not fetch API key: {e}")
        return []

    batch_filters  = [f"batch:{b}" for b in batches]
    tag_filters    = [f"tags:{t}" for t in tags]
    # Algolia facetFilters: inner list = OR, outer list = AND
    facet_filters  = [batch_filters, tag_filters]

    import json as _json
    params = "&".join([
        "query=",
        f"facetFilters={_json.dumps(facet_filters)}",
        f"hitsPerPage={hits_per_page}",
        "attributesToRetrieve=name,slug,website,one_liner,batch,tags,status",
    ])

    payload = {"requests": [{"indexName": YC_ALGOLIA_INDEX, "params": params}]}
    try:
        r = _requests.post(
            "https://45bwzj1sgc-dsn.algolia.net/1/indexes/*/queries",
            headers={
                "X-Algolia-Application-Id": YC_ALGOLIA_APP_ID,
                "X-Algolia-API-Key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        hits = r.json()["results"][0]["hits"]
        # Skip acquired / inactive companies
        websites = [
            h["website"] for h in hits
            if h.get("website") and h.get("status") not in ("Acquired", "Inactive", "Dead")
        ]
        print(f"    [yc] {len(hits)} hits → {len(websites)} active with websites")
        return websites
    except Exception as e:
        print(f"    [yc] algolia query failed: {e}")
        return []


# ── Sorsa helpers ─────────────────────────────────────────────────────────────

def _handle_to_id(handle: str) -> str | None:
    try:
        uid = username_to_id(handle.lstrip("@"))
        time.sleep(0.3)
        return uid
    except Exception as e:
        print(f"    [sorsa] username_to_id(@{handle}): {e}")
        return None


def _x_search_author_ids(query: str, max_results: int = 100,
                          min_followers: int = MIN_FOLLOWERS) -> list[str]:
    """
    Sorsa tweet search → unique author user IDs filtered by minimum followers.
    """
    try:
        tweets = search_tweets(query, order="popular", max_results=max_results)
    except Exception as e:
        print(f"    [sorsa] search_tweets({query!r}): {e}")
        return []

    seen: dict[str, int] = {}
    for t in tweets:
        if t.get("is_reply") or t.get("retweeted_status"):
            continue
        user = t.get("user", {})
        uid = user.get("id", "")
        followers = user.get("followers_count", 0)
        if uid and followers >= min_followers and uid not in seen:
            seen[uid] = followers
    return list(seen.keys())


# ── theme collector ───────────────────────────────────────────────────────────

def _collect_theme(theme_key: str, theme: dict, yc_only: bool = False) -> list[dict]:
    """
    Collect all candidate X user IDs for one theme.
    Returns dicts with {id, watchers, watcher_count, theme_label}.
    Pass yc_only=True to skip Exa and X sources and run only the YC Algolia step.
    """
    label = theme["label"]
    id_sources: dict[str, set[str]] = {}  # uid → set of source labels

    def _register(uid: str | None, source: str):
        if uid:
            id_sources.setdefault(uid, set()).add(source)

    if not yc_only:
        # 1. Exa neural search on seed URLs
        print(f"    exa similar ({len(theme['seed_urls'])} seeds)...")
        for seed_url in theme["seed_urls"]:
            for _, handle in _exa_similar(seed_url):
                if handle:
                    _register(_handle_to_id(handle), "exa_similar")
            time.sleep(0.5)

        # 2. Exa company keyword search
        print(f"    exa company search ({len(theme['exa_queries'])} queries)...")
        for q in theme["exa_queries"]:
            for _, handle in _exa_company_search(q):
                if handle:
                    _register(_handle_to_id(handle), "exa_company")
            time.sleep(0.5)

        # 3. X tweet search
        print(f"    x tweet search ({len(theme['x_queries'])} queries)...")
        for q in theme["x_queries"]:
            for uid in _x_search_author_ids(q):
                _register(uid, "x_search")
            time.sleep(1.0)

    # 4. YC Algolia — batch-specific, tag-filtered
    print(f"    yc algolia ({', '.join(theme['yc_tags'])})...")
    yc_websites = _yc_algolia_search(theme["yc_tags"])
    for website in yc_websites:
        handle = _resolve_website_to_handle(website)
        if handle:
            _register(_handle_to_id(handle), "yc")
        time.sleep(0.3)

    accounts = []
    for uid, sources in id_sources.items():
        source_list = [f"thematic:{theme_key}"] + sorted(sources)
        accounts.append({
            "id": uid,
            "watchers": source_list,
            "watcher_count": len(sources),
            "theme_label": label,
        })

    print(f"    → {len(accounts)} candidates for {label}")
    return accounts


# ── pre-sync filter ───────────────────────────────────────────────────────────

def _filter_accounts(accounts: list[dict]) -> list[dict]:
    """
    Drop accounts that are people (not projects), already have a token,
    or have too few followers to be worth tracking.
    """
    kept, dropped = [], []
    for a in accounts:
        reasons = []
        if a.get("account_type") != "project":
            reasons.append(f"type={a.get('account_type', 'unknown')}")
        if a.get("token_status") == "has token":
            reasons.append("has token")
        if (a.get("followers_count") or 0) < MIN_FOLLOWERS:
            reasons.append(f"followers={a.get('followers_count', 0)}")
        if reasons:
            dropped.append((a.get("username", a["id"]), reasons))
        else:
            kept.append(a)

    if dropped:
        print(f"\n  Pre-sync filter: dropped {len(dropped)} accounts")
        for name, reasons in dropped[:10]:  # show first 10 to avoid spam
            print(f"    - @{name}: {', '.join(reasons)}")
        if len(dropped) > 10:
            print(f"    ... and {len(dropped) - 10} more")

    return kept


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Thematic deal sourcing")
    parser.add_argument("--theme", choices=list(THEMES.keys()), help="Run a single theme")
    parser.add_argument("--yc-only", action="store_true", help="Skip Exa and X sources, run only the YC Algolia step")
    parser.add_argument("--dry-run", action="store_true", help="Print candidates, skip Notion sync")
    args = parser.parse_args()

    from datetime import datetime
    print(f"\n=== Thematic Search — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")

    init_db()
    known_ids = get_known_ids()

    themes_to_run = {args.theme: THEMES[args.theme]} if args.theme else THEMES

    all_accounts: list[dict] = []
    seen_ids: set[str] = set()

    for theme_key, theme in themes_to_run.items():
        print(f"\n{'─' * 55}")
        print(f"  Theme: {theme['label']}")
        print(f"{'─' * 55}")

        for acct in _collect_theme(theme_key, theme, yc_only=args.yc_only):
            uid = acct["id"]
            if uid in known_ids:
                continue
            if uid in seen_ids:
                # merge sources when the same account appears in multiple themes
                existing = next(a for a in all_accounts if a["id"] == uid)
                existing["watchers"] = list(set(existing["watchers"]) | set(acct["watchers"]))
                existing["watcher_count"] = len(
                    {s for s in existing["watchers"] if not s.startswith("thematic:")}
                )
                continue
            seen_ids.add(uid)
            all_accounts.append(acct)

    if not all_accounts:
        print("\nNo new accounts found.")
        return

    print(f"\n{'═' * 55}")
    print(f"  Total new candidates: {len(all_accounts)}")
    print(f"{'═' * 55}")

    if args.dry_run:
        for a in all_accounts:
            print(f"  {a['id']}  theme={a.get('theme_label', '')}  sources={a['watchers']}")
        print("\n[dry-run] Skipping enrich/analyze/Notion.")
        return

    print("\nEnriching profiles...")
    all_accounts = enrich_profiles(all_accounts)

    print("Fetching tweets...")
    all_accounts = enrich_tweets(all_accounts)

    print("Analyzing with Claude...")
    all_accounts = analyze_accounts(all_accounts)

    # Prepend theme label to Sector so it's a filterable tag in Notion
    for a in all_accounts:
        theme_label = a.get("theme_label", "")
        if theme_label:
            existing = a.get("sector", [])
            if theme_label not in existing:
                a["sector"] = [theme_label] + existing

    # Drop people, tokenised projects, and low-follower accounts
    all_accounts = _filter_accounts(all_accounts)

    if not all_accounts:
        print("\nAll candidates filtered out — nothing to sync.")
        return

    print(f"\nSyncing {len(all_accounts)} accounts to Notion...")
    sync_to_notion(all_accounts)

    added = sum(1 for a in all_accounts if a.get("notion_page_id"))
    print(f"\nDone. {added}/{len(all_accounts)} new accounts added to Notion.")


if __name__ == "__main__":
    main()
