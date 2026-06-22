"""
Find senior Coinbase people on X by searching tweets and filtering by bio.
Outputs a clean list of @handles suitable for founder_watchlist.txt.
"""

import sys
import re
import time
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from api.sorsa import search_tweets

SENIOR_TITLES = re.compile(
    r'\b(co-?founder|ceo|cto|coo|cpo|cso|vp\b|vice president|'
    r'head of|director|president|principal|general counsel|chief\b)',
    re.IGNORECASE,
)

# Simple queries — complex operators cause 0 results; filter programmatically
QUERIES = [
    'Coinbase "head of"',
    'Coinbase "VP of"',
    'Coinbase "co-founder"',
    'Coinbase director',
    'Coinbase CEO',
    'Coinbase CTO',
    'Coinbase "chief"',
    'Coinbase "years at"',
    'Coinbase "product" "engineering"',
]

found: dict[str, dict] = {}  # handle -> user info

for query in QUERIES:
    print(f"  searching: {query!r}", file=sys.stderr)
    try:
        tweets = search_tweets(query, order="popular", max_results=100)
    except Exception as e:
        print(f"    [warn] failed: {e}", file=sys.stderr)
        time.sleep(2)
        continue

    for t in tweets:
        # Skip retweets
        if t.get("retweeted_status"):
            continue

        user = t.get("user") or {}
        handle = (user.get("username") or "").strip()
        bio = (user.get("description") or "").strip()
        followers = user.get("followers_count", 0)
        name = (user.get("display_name") or "").strip()

        if not handle or not bio:
            continue

        bio_lower = bio.lower()

        # Must mention Coinbase in bio
        if "coinbase" not in bio_lower:
            continue

        # Must have a senior title in bio
        if not SENIOR_TITLES.search(bio):
            continue

        if handle.lower() == "coinbase":
            continue

        if handle not in found or followers > found[handle]["followers"]:
            found[handle] = {"name": name, "bio": bio, "followers": followers}

    time.sleep(0.5)

# Sort by followers descending
ranked = sorted(found.items(), key=lambda x: x[1]["followers"], reverse=True)

print(f"\n# ── Coinbase ──────────────────────────────────────────────────────────────────")
print(f"# Found {len(ranked)} accounts\n")

for handle, info in ranked:
    print(f"@{handle}")

print("\n\n# --- with bios ---\n")
for handle, info in ranked:
    print(f"@{handle:30s}  {info['followers']:>8,} followers  |  {info['bio'][:100]}")
