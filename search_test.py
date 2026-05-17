"""
Keyword search test — Sorsa API

Searches for recent tweets matching startup/launch keywords using the same
Sorsa API key already used by the main pipeline. No extra credentials needed.

Run:
  python search_test.py
"""

import sys
import time
import anthropic
from config import SORSA_API_KEY, ANTHROPIC_API_KEY
from state import init_db, get_known_ids, add_account
from api.notion import create_page, username_exists
from api.sorsa import get_profiles_batch, search_tweets

if not SORSA_API_KEY:
    sys.exit("Missing TweetScout_API_key in .env")
if not ANTHROPIC_API_KEY:
    sys.exit("Missing ANTHROPIC_API_KEY in .env")

# ── search config ─────────────────────────────────────────────────────────────
KEYWORDS = [
    "waitlist open",
    "launching beta",
    "alpha access",
    "now live",
    "we're launching",
]

# Twitter Advanced Search syntax — Sorsa supports the full operator set
QUERY = (
    "(" + " OR ".join(f'"{kw}"' for kw in KEYWORDS) + ")"
    " (crypto OR web3 OR defi OR protocol OR blockchain OR onchain)"
    " -filter:retweets lang:en"
)

ORDER         = "popular"  # "popular" or "latest"
MAX_RESULTS   = 500        # max tweets to fetch per run (pagination)
MIN_LIKES     = 20         # filter: skip low-engagement tweets
MIN_FOLLOWERS = 200        # filter: skip tiny accounts


def parse_tweets(tweets: list[dict]) -> list[dict]:
    """Flatten Sorsa tweet+user structure into simple dicts."""
    results = []
    for t in tweets:
        if t.get("is_reply") or t.get("retweeted_status"):
            continue
        user = t.get("user", {})
        results.append({
            "tweet_id":       t["id"],
            "tweet_text":     t.get("full_text", ""),
            "tweet_likes":    t.get("likes_count", 0),
            "tweet_retweets": t.get("retweet_count", 0),
            "tweet_views":    t.get("view_count", 0),
            "created_at":     t.get("created_at", ""),
            "author_id":      user.get("id", ""),
            "name":           user.get("display_name", ""),
            "username":       user.get("username", ""),
            "bio":            user.get("description", ""),
            "followers":      user.get("followers_count", 0),
            "tweet_count":    user.get("tweets_count", 0),
            "account_created": user.get("created_at", ""),
        })
    return results


# ── Claude analysis (same prompt as main pipeline) ────────────────────────────
_claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def analyze(tweet_text: str, bio: str) -> dict:
    prompt = f"""Analyze this crypto/startup ecosystem account.

Official bio: {bio}

Tweets:
{tweet_text}

Return exactly this format:

TYPE:
[project or person]

ONE-LINER:
[one sharp sentence: what this is and why it matters, max 15 words]

DESCRIPTION:
[2-3 sentence summary of what this account focuses on — their role, key themes, perspective]

SECTOR:
[comma-separated list from: DeFi, L1, L2, AI, Gaming, NFT, Infrastructure, DAO, VC, Social, RWA, Other]

TOKEN STATUS:
[exactly one of: has token / TGE planned / no token / unknown]

STAGE:
[exactly one of: pre-seed / seed / growth / unknown]

ENTITIES:
- Entity name (type)

Rules:
- TYPE must be exactly "project" or "person"
- SECTOR: pick only relevant ones from the list, max 3
- Entity types: project, token, VC, person, protocol, exchange, other"""

    resp = _claude.messages.create(
        model="claude-haiku-4-5",
        max_tokens=600,
        system="You analyze crypto and startup Twitter accounts for a venture capital deal-sourcing tool.",
        messages=[{"role": "user", "content": prompt}],
    )

    text = resp.content[0].text.strip()

    def section(start, end=None):
        if start not in text:
            return ""
        s = text.split(start)[1]
        if end and end in s:
            s = s.split(end)[0]
        return s.strip()

    type_raw = section("TYPE:", "ONE-LINER:").lower()
    account_type = "project" if "project" in type_raw else "person" if "person" in type_raw else "unknown"

    token_raw = section("TOKEN STATUS:", "STAGE:").lower()
    if "has token" in token_raw:
        token_status = "has token"
    elif "tge planned" in token_raw:
        token_status = "TGE planned"
    elif "no token" in token_raw:
        token_status = "no token"
    else:
        token_status = "unknown"

    stage_raw = section("STAGE:", "ENTITIES:").lower()
    stage = "pre-seed" if "pre-seed" in stage_raw else "seed" if "seed" in stage_raw else "growth" if "growth" in stage_raw else "unknown"

    sector_raw = section("SECTOR:", "TOKEN STATUS:")
    sectors = [s.strip() for s in sector_raw.split(",") if s.strip()]

    entities = [
        line.strip("- ").strip()
        for line in section("ENTITIES:").splitlines()
        if line.strip("- ").strip()
    ]

    return {
        "type":         account_type,
        "one_liner":    section("ONE-LINER:", "DESCRIPTION:"),
        "description":  section("DESCRIPTION:", "SECTOR:"),
        "sectors":      sectors,
        "token_status": token_status,
        "stage":        stage,
        "entities":     entities,
    }


# ── pretty printer ────────────────────────────────────────────────────────────
def print_result(r: dict, analysis: dict, idx: int):
    sep = "─" * 60
    print(f"\n{sep}")
    print(f"  RESULT #{idx}")
    print(sep)
    print(f"  Account  : @{r['username']} ({r['name']})")
    print(f"  Profile  : https://x.com/{r['username']}")
    print(f"  Followers: {r['followers']:,}  |  Tweets: {r['tweet_count']:,}")
    print(f"  Bio      : {r['bio'][:120]}")
    print()
    print(f"  MATCHED TWEET ({r['tweet_likes']} likes / {r['tweet_retweets']} RTs / {r['tweet_views']:,} views):")
    print(f"  \"{r['tweet_text'][:200]}\"")
    print(f"  https://x.com/{r['username']}/status/{r['tweet_id']}")
    print()
    print(f"  ── Claude Analysis ──")
    print(f"  Type        : {analysis['type']}")
    print(f"  One-liner   : {analysis['one_liner']}")
    print(f"  Description : {analysis['description']}")
    print(f"  Sector      : {', '.join(analysis['sectors']) or 'n/a'}")
    print(f"  Stage       : {analysis['stage']}")
    print(f"  Token       : {analysis['token_status']}")
    if analysis["entities"]:
        print(f"  Entities    :")
        for e in analysis["entities"]:
            print(f"               - {e}")


# ── Notion push ───────────────────────────────────────────────────────────────
def push_new_projects(analyzed: list[tuple[dict, dict]]):
    init_db()
    known_ids = get_known_ids()

    seen: set[str] = set()
    candidates: list[tuple[dict, dict]] = []
    for r, analysis in analyzed:
        uid = r["author_id"]
        if analysis["type"] != "project" or uid in known_ids or uid in seen:
            continue
        if analysis.get("token_status") == "has token":
            continue
        seen.add(uid)
        candidates.append((r, analysis))

    if not candidates:
        print("\nNo new projects to add to Notion.")
        return

    print(f"\n{len(candidates)} new project(s) found via search. Enriching profiles...")

    ids = [r["author_id"] for r, _ in candidates]
    profiles = {p["id"]: p for p in get_profiles_batch(ids)}

    added = 0
    for r, analysis in candidates:
        uid = r["author_id"]
        p = profiles.get(uid, {})

        account = {
            "id":               uid,
            "display_name":     p.get("display_name") or r["name"],
            "username":         p.get("username") or r["username"],
            "description":      p.get("description") or r["bio"],
            "followers_count":  p.get("followers_count") if p.get("followers_count") is not None else r["followers"],
            "followings_count": p.get("followings_count"),
            "tweets_count":     p.get("tweets_count") if p.get("tweets_count") is not None else r["tweet_count"],
            "verified":         p.get("verified", False),
            "created_at":       p.get("created_at") or r["account_created"],
            "last_tweet_date":  r["created_at"],
            "watcher_count":    0,
            "watchers":         [],
            "tweet_analysis":   analysis["description"],
            "entities":         analysis["entities"],
            "account_type":     "project",
            "one_liner":        analysis["one_liner"],
            "sector":           analysis["sectors"],
            "token_status":     analysis["token_status"],
            "stage":            analysis["stage"],
        }

        try:
            if username_exists(account["username"]):
                print(f"  [skip] @{account['username']} already in Notion")
                continue
            page_id = create_page(account)
            add_account(uid, page_id)
            added += 1
            print(f"  + Added @{account['username']} to Notion")
        except Exception as e:
            print(f"  ! Failed @{account['username']}: {e}")
        time.sleep(0.3)

    print(f"{added}/{len(candidates)} project(s) added to Notion.")


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Searching X for:\n  {QUERY}\n")

    raw     = search_tweets(QUERY, ORDER, MAX_RESULTS)
    results = parse_tweets(raw)

    print(f"Found {len(results)} tweet(s). Filtering (min {MIN_LIKES} likes, min {MIN_FOLLOWERS} followers)...")

    filtered = [
        r for r in results
        if r["tweet_likes"] >= MIN_LIKES and r["followers"] >= MIN_FOLLOWERS
    ]
    filtered.sort(key=lambda x: x["tweet_likes"], reverse=True)

    print(f"{len(filtered)} passed filters. Running Claude analysis...\n")

    if not filtered:
        print("No results passed filters. Try lowering MIN_LIKES / MIN_FOLLOWERS.")
        return

    analyzed: list[tuple[dict, dict]] = []
    for i, r in enumerate(filtered, 1):
        analysis = analyze(r["tweet_text"], r["bio"])
        print_result(r, analysis, i)
        analyzed.append((r, analysis))

    print(f"\n{'─' * 60}")
    print(f"Done. {len(filtered)} result(s) shown.")

    push_new_projects(analyzed)


if __name__ == "__main__":
    main()
