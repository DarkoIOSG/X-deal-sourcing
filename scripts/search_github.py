"""
GitHub repository search — find early-stage crypto/DeFi projects by recent repo activity.

Searches GitHub for newly created or recently pushed repositories matching
crypto/web3 keywords. New repos with real code are a strong early-stage signal.

Run:
  python3 scripts/search_github.py
"""

import sys
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

# ── config ────────────────────────────────────────────────────────────────────
KEYWORDS = [
    "defi protocol",
    "prediction market",
    "stablecoin",
    "perpetuals dex",
    "onchain payments",
    "rwa tokenization",
    "ai agent defi",
]

DAYS_BACK      = 90     # only repos created or pushed in the last N days
MIN_STARS      = 5      # skip repos with no traction at all
MAX_RESULTS    = 50     # results per keyword
SHOW_README    = False  # set True to fetch and print README snippets (slower)

# GitHub API — no token needed for read-only, but rate-limited to 60 req/hr
# Add a token for 5000 req/hr: create one at github.com/settings/tokens (no scopes needed)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

BASE_URL = "https://api.github.com/search/repositories"

# ── helpers ───────────────────────────────────────────────────────────────────

def search_repos(keyword: str, days_back: int = 30, max_results: int = 50) -> list[dict]:
    since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    query = f"{keyword} created:>{since}"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(max_results, 100),
    }
    r = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
    if r.status_code == 403:
        print("  [rate limited] Add a GITHUB_TOKEN to increase limit to 5000 req/hr")
        return []
    r.raise_for_status()
    return r.json().get("items", [])


def fetch_readme(full_name: str) -> str:
    url = f"https://api.github.com/repos/{full_name}/readme"
    r = requests.get(url, headers=HEADERS, timeout=15)
    if not r.ok:
        return ""
    import base64
    content = r.json().get("content", "")
    try:
        return base64.b64decode(content).decode("utf-8", errors="ignore")[:1000]
    except Exception:
        return ""


def print_repo(repo: dict, idx: int):
    sep = "─" * 65
    created = repo["created_at"][:10]
    pushed  = repo["pushed_at"][:10]
    print(f"\n{sep}")
    print(f"  #{idx}  {repo['full_name']}")
    print(sep)
    print(f"  Stars    : {repo['stargazers_count']}  |  Forks: {repo['forks_count']}  |  Language: {repo.get('language') or 'n/a'}")
    print(f"  Created  : {created}  |  Last push: {pushed}")
    print(f"  URL      : {repo['html_url']}")
    if repo.get("description"):
        print(f"  Desc     : {repo['description'][:120]}")
    if repo.get("topics"):
        print(f"  Topics   : {', '.join(repo['topics'][:8])}")
    if SHOW_README:
        readme = fetch_readme(repo["full_name"])
        if readme:
            print(f"  README   : {readme[:300].strip()}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    seen: set[str] = set()

    for keyword in KEYWORDS:
        print(f"\n{'═' * 65}")
        print(f"  Searching: \"{keyword}\"  (last {DAYS_BACK} days, min {MIN_STARS} stars)")
        print(f"{'═' * 65}")

        repos = search_repos(keyword, DAYS_BACK, MAX_RESULTS)
        filtered = [
            r for r in repos
            if r["stargazers_count"] >= MIN_STARS
            and r["full_name"] not in seen
            and not r["fork"]
        ]

        if not filtered:
            print("  No results.")
            continue

        for i, repo in enumerate(filtered, 1):
            seen.add(repo["full_name"])
            print_repo(repo, i)

    print(f"\n{'═' * 65}")
    print(f"  Done. {len(seen)} unique repo(s) across {len(KEYWORDS)} keyword(s).")
    print(f"{'═' * 65}")


if __name__ == "__main__":
    main()
