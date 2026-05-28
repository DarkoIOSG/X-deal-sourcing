"""
GitHub repository search — find early-stage crypto/DeFi projects by recent repo activity.

Searches GitHub for newly created or recently pushed repositories matching
crypto/web3 keywords. New repos with real code are a strong early-stage signal.

For each repo, the script attempts to resolve the project's X/Twitter handle via:
  1. GitHub owner profile (org or user) — has a twitter_username field
  2. Repo homepage URL — fetched via Exa, parsed for X links
  3. README — parsed for X links
  4. Exa company search fallback

Run:
  python3 scripts/search_github.py                  # print results only
  python3 scripts/search_github.py --push           # resolve handles + push to Notion
  python3 scripts/search_github.py --push --dry-run # resolve handles, skip Notion writes
"""

import sys
import os
import re
import time
import base64
import argparse
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from exa_py import Exa
from config import EXA_API_KEY
from api.sorsa import username_to_id
from pipeline.enrich import enrich_profiles, enrich_tweets
from pipeline.analyze import analyze_accounts
from pipeline.notion_sync import sync_to_notion
from state import init_db, get_known_ids

# ── config ────────────────────────────────────────────────────────────────────

KEYWORDS = [
    "defi protocol",
    "prediction market",
    "stablecoin",
    "perpetuals dex",
    "onchain payments",
    "rwa tokenization",
    "ai agent defi",
    # alt ecosystems
    "arc protocol defi",
    "arc ecosystem dapp",
    "canton network daml",
    "canton network defi",
    "daml smart contract",
    "tempo network blockchain",
    "tempo protocol defi",
]

DAYS_BACK   = 90   # only repos created or pushed in the last N days
MIN_STARS   = 5    # skip repos with no traction at all
MAX_RESULTS = 50   # results per keyword

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GH_HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    GH_HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

BASE_URL = "https://api.github.com/search/repositories"

# Matches twitter.com/handle or x.com/handle, skips non-profile paths
_HANDLE_RE = re.compile(
    r'(?:twitter|x)\.com/'
    r'(?!share|intent|home|search|hashtag|status|i/|messages|explore|notifications|settings|'
    r'privacy|tos|about|help|download|login|signup|compose)'
    r'([A-Za-z0-9_]{1,50})',
    re.IGNORECASE,
)

_exa: Exa | None = None


def _get_exa() -> Exa:
    global _exa
    if _exa is None:
        _exa = Exa(api_key=EXA_API_KEY)
    return _exa


def _extract_handle(text: str) -> str | None:
    for m in _HANDLE_RE.finditer(text):
        h = m.group(1).rstrip("/")
        if h.lower() not in ("status", "share", "intent"):
            return h
    return None


# ── GitHub helpers ────────────────────────────────────────────────────────────

def search_repos(keyword: str, days_back: int = DAYS_BACK,
                 max_results: int = MAX_RESULTS) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    params = {
        "q": f"{keyword} created:>{since}",
        "sort": "stars",
        "order": "desc",
        "per_page": min(max_results, 100),
    }
    r = requests.get(BASE_URL, headers=GH_HEADERS, params=params, timeout=30)
    if r.status_code == 403:
        print("  [rate limited] Add a GITHUB_TOKEN to .env for 5000 req/hr")
        return []
    r.raise_for_status()
    return r.json().get("items", [])


def fetch_readme(full_name: str) -> str:
    try:
        r = requests.get(f"https://api.github.com/repos/{full_name}/readme",
                         headers=GH_HEADERS, timeout=15)
        if not r.ok:
            return ""
        return base64.b64decode(r.json().get("content", "")).decode("utf-8", errors="ignore")[:3000]
    except Exception:
        return ""


def _github_owner_twitter(login: str, owner_type: str) -> str | None:
    """Call the GitHub org or user endpoint — both expose a twitter_username field."""
    endpoint = "orgs" if owner_type == "Organization" else "users"
    try:
        r = requests.get(f"https://api.github.com/{endpoint}/{login}",
                         headers=GH_HEADERS, timeout=15)
        if r.ok:
            return r.json().get("twitter_username") or None
    except requests.exceptions.Timeout:
        pass
    return None


# ── Exa helpers ───────────────────────────────────────────────────────────────

def _exa_fetch_handle(url: str) -> str | None:
    """Fetch a URL via Exa and extract the first X handle from the page text."""
    try:
        res = _get_exa().get_contents([url], text={"max_characters": 2000})
        if res.results:
            text = (getattr(res.results[0], "text", "") or "") + " " + url
            return _extract_handle(text)
    except Exception:
        pass
    return None


def _exa_search_handle(repo_name: str) -> str | None:
    """Exa company search fallback — find the project's website and extract its X handle."""
    try:
        res = _get_exa().search(
            f"{repo_name} crypto blockchain official",
            type="auto",
            category="company",
            num_results=3,
            contents={"text": {"max_characters": 1500}},
        )
        for r in res.results:
            text = (getattr(r, "text", "") or "") + " " + r.url
            h = _extract_handle(text)
            if h:
                return h
    except Exception:
        pass
    return None


# ── Handle resolution ─────────────────────────────────────────────────────────

def resolve_x_handle(repo: dict) -> tuple[str | None, str]:
    """
    Try to find the X/Twitter handle for a GitHub repo's project.
    Returns (handle_or_None, source_label).

    Resolution order (cheapest/most reliable first):
      1. GitHub owner profile — twitter_username field
      2. Repo homepage — Exa content fetch + link extraction
      3. README — parse for X links
      4. Exa company search — last resort
    """
    owner = repo["owner"]

    # 1. GitHub owner profile
    handle = _github_owner_twitter(owner["login"], owner["type"])
    if handle:
        return handle, "github_profile"

    # 2. Repo homepage
    homepage = (repo.get("homepage") or "").strip()
    if homepage and homepage.startswith("http"):
        handle = _exa_fetch_handle(homepage)
        if handle:
            return handle, "homepage"

    # 3. README
    readme = fetch_readme(repo["full_name"])
    if readme:
        handle = _extract_handle(readme)
        if handle:
            return handle, "readme"

    # 4. Exa company search
    handle = _exa_search_handle(repo["name"])
    if handle:
        return handle, "exa_search"

    return None, "not_found"


# ── Console output ────────────────────────────────────────────────────────────

def print_repo(repo: dict, idx: int, handle: str | None = None, source: str = ""):
    sep = "─" * 65
    created = repo["created_at"][:10]
    pushed  = repo["pushed_at"][:10]
    print(f"\n{sep}")
    print(f"  #{idx}  {repo['full_name']}")
    print(sep)
    print(f"  Stars  : {repo['stargazers_count']}  |  Forks: {repo['forks_count']}  |  Language: {repo.get('language') or 'n/a'}")
    print(f"  Created: {created}  |  Last push: {pushed}")
    print(f"  URL    : {repo['html_url']}")
    if repo.get("description"):
        print(f"  Desc   : {repo['description'][:120]}")
    if repo.get("topics"):
        print(f"  Topics : {', '.join(repo['topics'][:8])}")
    if handle:
        print(f"  X      : @{handle}  [{source}]")
    else:
        print(f"  X      : not found")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GitHub crypto repo search")
    parser.add_argument("--push",    action="store_true", help="Resolve X handles and push to Notion")
    parser.add_argument("--dry-run", action="store_true", help="With --push: resolve handles but skip Notion writes")
    args = parser.parse_args()

    seen_repos: set[str] = set()
    all_repos:  list[dict] = []

    for keyword in KEYWORDS:
        print(f"\n{'═' * 65}")
        print(f"  Searching: \"{keyword}\"  (last {DAYS_BACK} days, min {MIN_STARS} stars)")
        print(f"{'═' * 65}")

        repos = search_repos(keyword)
        filtered = [
            r for r in repos
            if r["stargazers_count"] >= MIN_STARS
            and r["full_name"] not in seen_repos
            and not r["fork"]
        ]

        if not filtered:
            print("  No results.")
            continue

        for i, repo in enumerate(filtered, 1):
            seen_repos.add(repo["full_name"])
            all_repos.append(repo)

            if args.push:
                handle, source = resolve_x_handle(repo)
                repo["_x_handle"] = handle
                repo["_x_source"] = source
                print_repo(repo, i, handle, source)
                time.sleep(0.5)
            else:
                print_repo(repo, i)

    print(f"\n{'═' * 65}")
    print(f"  Found {len(all_repos)} unique repo(s) across {len(KEYWORDS)} keyword(s).")
    print(f"{'═' * 65}")

    if not args.push:
        print("\n  Tip: run with --push to resolve X handles and sync to Notion.")
        return

    # ── Pipeline ──────────────────────────────────────────────────────────────
    init_db()
    known_ids = get_known_ids()

    accounts: list[dict] = []
    seen_ids: set[str] = set()

    print("\nResolving Sorsa user IDs...")
    for repo in all_repos:
        handle = repo.get("_x_handle")
        if not handle:
            continue
        try:
            uid = username_to_id(handle)
            time.sleep(0.3)
        except Exception as e:
            print(f"  [sorsa] @{handle}: {e}")
            continue

        if uid in known_ids:
            print(f"  [skip] @{handle} already in DB")
            continue
        if uid in seen_ids:
            continue

        seen_ids.add(uid)
        accounts.append({
            "id":           uid,
            "watchers":     [f"github:{repo['full_name']}"],
            "watcher_count": 1,
        })

    if not accounts:
        print("No new accounts to push.")
        return

    print(f"\n{len(accounts)} new account(s) to process.")

    if args.dry_run:
        for a in accounts:
            print(f"  {a['id']}  source={a['watchers'][0]}")
        print("\n[dry-run] Skipping enrich/analyze/Notion.")
        return

    print("\nEnriching profiles...")
    accounts = enrich_profiles(accounts)

    print("Fetching tweets...")
    accounts = enrich_tweets(accounts)

    print("Analyzing with Claude...")
    accounts = analyze_accounts(accounts)

    print("Syncing to Notion...")
    sync_to_notion(accounts)

    added = sum(1 for a in accounts if a.get("notion_page_id"))
    print(f"\nDone. {added}/{len(accounts)} new accounts added to Notion.")


if __name__ == "__main__":
    main()
