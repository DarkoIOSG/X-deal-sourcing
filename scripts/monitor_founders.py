"""
Founder bio monitoring — track stealth signals from crypto unicorn employees.

Two complementary approaches:

  B. Bio snapshot + diff (founder_watchlist.txt)
     Daily fetch of X profiles for every handle in the file.
     Stores bios in SQLite, diffs against previous snapshot, and flags changes
     that suggest someone is "going stealth" — blank bio, "ex-" prefix added,
     "building" / "stealth" / "new chapter" keywords appearing, etc.

  C. Departure announcement search
     Sorsa tweet search + Exa LinkedIn search for people actively announcing
     they are leaving a target unicorn to build something new. Catches founders
     NOT in your watchlist.

founder_watchlist.txt format (one entry per line, comments with #):
  https://x.com/handle
  @handle
  handle

Run:
  python3 scripts/monitor_founders.py           # run B + C, print report
  python3 scripts/monitor_founders.py --b-only  # bio diff only
  python3 scripts/monitor_founders.py --c-only  # departure search only
"""

import re
import sys
import time
import sqlite3
import argparse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from exa_py import Exa
from config import EXA_API_KEY, DB_PATH
from api.sorsa import username_to_id, get_profiles_batch, search_tweets

# ── config ────────────────────────────────────────────────────────────────────

FOUNDER_WATCHLIST = Path(__file__).parent.parent / "founder_watchlist.txt"

# Companies whose alumni we want to track for departure signals (Option C)
TARGET_COMPANIES = [
    "Coinbase", "Binance", "Uniswap", "dYdX", "Aave", "MakerDAO",
    "Solana Labs", "Optimism", "Arbitrum", "StarkWare", "Matter Labs",
    "Polygon", "LayerZero", "Chainlink", "Alchemy", "ConsenSys",
    "Fireblocks", "Circle", "EigenLayer", "Hyperliquid", "Celestia",
    "Pendle", "OKX", "Bybit", "Kraken", "Ethereum Foundation",
    "Securitize", "Paxos", "Anchorage",
]

# Bio keywords that suggest a founder is going stealth / starting something new
_STEALTH_RE = re.compile(
    r'\b(?:stealth|building|founding|co-?founding|new\s+chapter|'
    r'ex[-\s]|formerly|prev(?:iously)?|left\s+\w|starting\s+something|'
    r'working\s+on\s+something|what\'?s?\s+next)\b',
    re.IGNORECASE,
)

# Sorsa + Exa departure search queries (Option C)
_X_DEPARTURE_QUERIES = [
    # broad departure + crypto signal — one big OR to minimise API calls
    '("left" OR "leaving" OR "after X years" OR "new chapter") '
    '(Coinbase OR Uniswap OR dYdX OR Aave OR Binance OR "Solana Labs" OR Optimism OR Arbitrum) '
    'building -filter:retweets lang:en',

    '("going stealth" OR "building something" OR "starting something") '
    '(crypto OR defi OR blockchain OR web3) -filter:retweets lang:en',

    '"excited to announce" ("left" OR "leaving") (crypto OR defi OR web3) -filter:retweets lang:en',
]

_LINKEDIN_DEPARTURE_QUERIES = [
    '"left" "to build" crypto defi blockchain',
    '"new chapter" building crypto defi',
    '"after" years "excited to announce" crypto raised seed',
    '"going stealth" crypto blockchain',
]

# ── SQLite helpers ────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_founder_tables():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS founder_bio_snapshots (
                handle      TEXT PRIMARY KEY,
                user_id     TEXT,
                bio         TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                updated_at  TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS founder_bio_changes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                handle      TEXT NOT NULL,
                changed_at  TEXT NOT NULL,
                old_bio     TEXT,
                new_bio     TEXT,
                signal_type TEXT
            )
        """)


def load_snapshots() -> dict[str, dict]:
    """Return {handle: {user_id, bio, display_name, updated_at}}."""
    with _conn() as con:
        rows = con.execute(
            "SELECT handle, user_id, bio, display_name, updated_at FROM founder_bio_snapshots"
        ).fetchall()
    return {
        r[0]: {"user_id": r[1], "bio": r[2], "display_name": r[3], "updated_at": r[4]}
        for r in rows
    }


def save_snapshot(handle: str, user_id: str, bio: str, display_name: str):
    with _conn() as con:
        con.execute("""
            INSERT INTO founder_bio_snapshots (handle, user_id, bio, display_name, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(handle) DO UPDATE SET
                user_id      = excluded.user_id,
                bio          = excluded.bio,
                display_name = excluded.display_name,
                updated_at   = excluded.updated_at
        """, (handle, user_id, bio, display_name, datetime.now().isoformat()))


def log_change(handle: str, old_bio: str, new_bio: str, signal_type: str):
    with _conn() as con:
        con.execute("""
            INSERT INTO founder_bio_changes (handle, changed_at, old_bio, new_bio, signal_type)
            VALUES (?, ?, ?, ?, ?)
        """, (handle, datetime.now().isoformat(), old_bio, new_bio, signal_type))


# ── watchlist parsing ─────────────────────────────────────────────────────────

def load_founder_handles() -> list[str]:
    """Read founder_watchlist.txt, return clean list of handles."""
    if not FOUNDER_WATCHLIST.exists():
        return []

    handles = []
    for raw in FOUNDER_WATCHLIST.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # https://x.com/handle or https://twitter.com/handle
        m = re.search(r'(?:x|twitter)\.com/([A-Za-z0-9_]+)', line)
        if m:
            handles.append(m.group(1))
            continue
        # @handle or bare handle
        handles.append(line.lstrip("@"))
    return handles


# ── stealth signal detection ──────────────────────────────────────────────────

def classify_change(old_bio: str, new_bio: str) -> str | None:
    """
    Return a signal label if the bio change looks like a departure/stealth signal,
    otherwise return None (routine update, not interesting).
    """
    old_lower = old_bio.lower()
    new_lower = new_bio.lower()

    # Bio went blank or very short — classic "going dark"
    if len(old_bio) > 30 and len(new_bio) < 15:
        return "bio_cleared"

    # Stealth keyword appeared in new bio
    if _STEALTH_RE.search(new_bio) and not _STEALTH_RE.search(old_bio):
        return "stealth_keyword"

    # "ex-" or "formerly" appeared (explicit departure signal)
    if re.search(r'\bex[-\s]|\bformerly\b|\bpreviously\b', new_lower) and \
       not re.search(r'\bex[-\s]|\bformerly\b|\bpreviously\b', old_lower):
        return "ex_prefix_added"

    # A target company name was in the old bio but is gone
    for company in TARGET_COMPANIES:
        if company.lower() in old_lower and company.lower() not in new_lower:
            return f"removed_{company.replace(' ', '_').lower()}"

    # Changed but no strong signal — still record it for manual review
    if old_bio != new_bio:
        return "bio_changed"

    return None


# ── Option B: bio snapshot + diff ────────────────────────────────────────────

def run_bio_diff() -> list[dict]:
    """
    Fetch current X bios for all founders in the watchlist.
    Diff against stored snapshots. Return list of change dicts.
    """
    handles = load_founder_handles()
    if not handles:
        print("  [warn] founder_watchlist.txt is empty — nothing to monitor.")
        print("         Add X handles (one per line) to start tracking.")
        return []

    print(f"  Loaded {len(handles)} handles from founder_watchlist.txt")
    snapshots = load_snapshots()

    # Resolve handles to IDs (use cached value if available)
    handle_to_id: dict[str, str] = {}
    for h in handles:
        cached = snapshots.get(h, {}).get("user_id")
        if cached:
            handle_to_id[h] = cached
        else:
            try:
                uid = username_to_id(h)
                handle_to_id[h] = uid
                time.sleep(0.3)
            except Exception as e:
                print(f"    [sorsa] @{h}: {e}")

    if not handle_to_id:
        return []

    # Batch fetch profiles
    ids = list(handle_to_id.values())
    profiles = get_profiles_batch(ids)
    id_to_profile = {p["id"]: p for p in profiles}

    changes = []
    for handle, uid in handle_to_id.items():
        profile = id_to_profile.get(uid)
        if not profile:
            continue

        current_bio   = (profile.get("description") or "").strip()
        display_name  = (profile.get("display_name") or profile.get("name") or "").strip()
        previous      = snapshots.get(handle, {})
        previous_bio  = previous.get("bio", None)

        save_snapshot(handle, uid, current_bio, display_name)

        if previous_bio is None:
            # First time we've seen this handle — just store, no alert
            continue

        signal = classify_change(previous_bio, current_bio)
        if signal is None:
            continue

        log_change(handle, previous_bio, current_bio, signal)
        changes.append({
            "handle":       handle,
            "display_name": display_name,
            "signal":       signal,
            "old_bio":      previous_bio,
            "new_bio":      current_bio,
        })

    return changes


# ── Option C: departure announcement search ───────────────────────────────────

_exa: Exa | None = None


def _get_exa() -> Exa:
    global _exa
    if _exa is None:
        _exa = Exa(api_key=EXA_API_KEY)
    return _exa


def _search_x_departures() -> list[dict]:
    """Sorsa tweet search for departure announcements."""
    results = []
    for query in _X_DEPARTURE_QUERIES:
        try:
            tweets = search_tweets(query, order="latest", max_results=30)
        except Exception as e:
            print(f"    [sorsa] {query[:60]!r}: {e}")
            continue

        for t in tweets:
            if t.get("is_reply") or t.get("retweeted_status"):
                continue
            user   = t.get("user", {})
            handle = user.get("screen_name") or user.get("username") or ""
            text   = t.get("full_text") or t.get("text") or ""
            if handle and text:
                results.append({
                    "source":   "x_tweet",
                    "handle":   handle,
                    "name":     user.get("name", ""),
                    "bio":      user.get("description", ""),
                    "followers": user.get("followers_count", 0),
                    "text":     text[:280],
                    "url":      f"https://x.com/{handle}",
                })
        time.sleep(1.0)

    # Deduplicate by handle, keep highest-follower appearance
    seen: dict[str, dict] = {}
    for r in results:
        h = r["handle"]
        if h not in seen or r["followers"] > seen[h]["followers"]:
            seen[h] = r
    return list(seen.values())


def _search_linkedin_departures() -> list[dict]:
    """Exa LinkedIn search for departure + new venture announcements."""
    results = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    for query in _LINKEDIN_DEPARTURE_QUERIES:
        try:
            res = _get_exa().search(
                query,
                type="neural",
                num_results=5,
                include_domains=["linkedin.com"],
                contents={"text": {"max_characters": 500}},
            )
        except Exception as e:
            print(f"    [exa-li] {query[:60]!r}: {e}")
            continue

        for r in res.results:
            pub_raw = getattr(r, "published_date", None)
            if pub_raw:
                try:
                    pub_dt = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
                    if pub_dt < cutoff:
                        continue
                except Exception:
                    pass

            title = (getattr(r, "title", "") or "").strip()
            text  = (getattr(r, "text",  "") or "").strip()[:300]
            results.append({
                "source": "linkedin",
                "title":  title,
                "text":   text,
                "url":    r.url,
            })
        time.sleep(0.5)

    # Deduplicate by URL
    seen_urls: set[str] = set()
    deduped = []
    for r in results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            deduped.append(r)
    return deduped


# ── report printing ───────────────────────────────────────────────────────────

def print_bio_changes(changes: list[dict]):
    if not changes:
        print("  No bio changes detected.")
        return

    print(f"\n  {'─' * 68}")
    print(f"  {len(changes)} bio change(s) detected")
    print(f"  {'─' * 68}")

    for c in changes:
        signal_tag = f"[{c['signal']}]"
        print(f"\n  @{c['handle']}  {c['display_name']}  {signal_tag}")
        print(f"    OLD: {c['old_bio'] or '(empty)'}")
        print(f"    NEW: {c['new_bio'] or '(empty)'}")


def print_departure_signals(x_results: list[dict], li_results: list[dict]):
    total = len(x_results) + len(li_results)
    if total == 0:
        print("  No departure signals found.")
        return

    print(f"\n  {'─' * 68}")
    print(f"  {total} departure signal(s) found")
    print(f"  {'─' * 68}")

    for r in x_results:
        print(f"\n  [X] @{r['handle']}  {r['name']}  ({r['followers']:,} followers)")
        if r["bio"]:
            print(f"    Bio  : {r['bio'][:120]}")
        print(f"    Tweet: {r['text'][:200]}")
        print(f"    URL  : {r['url']}")

    for r in li_results:
        print(f"\n  [LinkedIn] {r['title']}")
        if r["text"]:
            print(f"    {r['text'][:200]}")
        print(f"    URL  : {r['url']}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Founder bio monitor — stealth signal detection")
    parser.add_argument("--b-only", action="store_true", help="Bio diff only (skip departure search)")
    parser.add_argument("--c-only", action="store_true", help="Departure search only (skip bio diff)")
    args = parser.parse_args()

    init_founder_tables()

    run_b = not args.c_only
    run_c = not args.b_only

    print(f"\n{'═' * 68}")
    print(f"  Founder Monitor — {date.today().isoformat()}")
    print(f"{'═' * 68}")

    # ── Option B ──────────────────────────────────────────────────────────────
    bio_changes = []
    if run_b:
        print("\n[B] Bio snapshot + diff")
        bio_changes = run_bio_diff()
        print_bio_changes(bio_changes)

    # ── Option C ──────────────────────────────────────────────────────────────
    x_departures, li_departures = [], []
    if run_c:
        print("\n[C] Departure announcement search")
        print("  Searching X...")
        x_departures = _search_x_departures()
        print(f"    {len(x_departures)} unique accounts found")

        print("  Searching LinkedIn...")
        li_departures = _search_linkedin_departures()
        print(f"    {len(li_departures)} LinkedIn results found")

        print_departure_signals(x_departures, li_departures)

    # ── summary ───────────────────────────────────────────────────────────────
    print(f"\n{'═' * 68}")
    total_signals = len(bio_changes) + len(x_departures) + len(li_departures)

    high_priority = [c for c in bio_changes if c["signal"] in
                     ("bio_cleared", "stealth_keyword", "ex_prefix_added")]
    if high_priority:
        print(f"  *** {len(high_priority)} HIGH-PRIORITY bio change(s) — likely going stealth ***")
        for c in high_priority:
            print(f"      @{c['handle']}  [{c['signal']}]")

    print(f"  Total signals: {total_signals}  "
          f"(bio changes: {len(bio_changes)}, X: {len(x_departures)}, LinkedIn: {len(li_departures)})")
    print(f"{'═' * 68}\n")


if __name__ == "__main__":
    main()
