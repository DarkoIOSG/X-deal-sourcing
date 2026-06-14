"""
Google News RSS search — find early-stage crypto/DeFi projects via news signals.

Monitors Google News RSS for funding announcements and product launches in
crypto/web3. News coverage is a distinct signal from GitHub stars or tweets —
it catches projects the moment they go public with a raise or launch.

For each article the script:
  1. Extracts the likely company/project name from the headline
  2. Optionally resolves its X/Twitter handle via Exa
  3. Optionally pushes to Notion via the standard pipeline

Run:
  python3 scripts/search_google_news.py                  # print results only
  python3 scripts/search_google_news.py --push           # resolve handles + push to Notion
  python3 scripts/search_google_news.py --push --dry-run # resolve handles, skip Notion writes
"""

import re
import sys
import time
import argparse
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
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

# ── config ────────────────────────────────────────────────────────────────────

DAYS_BACK = 14  # only articles published in the last N days

QUERIES = [
    # funding signals — "million" ensures "raises" is about money, not opinions
    '"seed round" defi protocol',
    '"seed round" web3 startup',
    '"pre-seed" crypto blockchain',
    '"raises" million stablecoin startup',
    '"raises" million "prediction market" protocol',
    '"raises" million perpetuals dex',
    '"raises" million "onchain payments"',
    '"raises" million "rwa tokenization"',
    '"raises" million "ai agent" defi',
    # launch signals — "startup" keeps out incumbents (Visa, Tether, etc.)
    '"launches" defi protocol startup',
    '"launches" perpetuals crypto startup',
    '"launches" stablecoin startup',
    '"announces" "onchain payments" startup',
    # alt ecosystems
    '"raises" "arc protocol"',
    '"raises" "canton network"',
    '"raises" "tempo network" blockchain',
]

_RSS_BASE = "https://news.google.com/rss/search"

# Action verbs used to split headlines and isolate the company name.
# Both present tense ("raises") and past tense ("raised") are included because
# news headlines use both styles.
_ACTION_VERBS = (
    "raises", "raised",
    "secures", "secured",
    "closes", "closed",
    "launches", "launched",
    "announces", "announced",
    "unveils", "unveiled",
    "debuts", "debuted",
    "receives", "received",
    "completes", "completed",
    "bags", "bagged",
    "lands", "landed",
    "nabs", "nabbed",
)

# Prefixes that precede a company name but are not part of it
_NOISE_PREFIX_RE = re.compile(
    r'^(?:new\s+|the\s+|exclusive[:\s]+|breaking[:\s]+|report[:\s]+|'
    r'(?:blockchain|defi|crypto|web3|nft|fintech|onchain|web3\s+fintech)\s+startup\s+)',
    re.IGNORECASE,
)

# Descriptor words that separate generic context from the actual project name.
# When walking backward from the verb, hitting one of these marks where the name ends.
# NOTE: "protocol" is intentionally excluded — it's often part of the project name (e.g. "XYZ Protocol").
_DESCRIPTOR_WORDS = frozenset({
    "startup", "firm", "company", "developer", "infrastructure",
    "builder", "provider", "venture", "unit", "arm", "division",
    "backed", "funded", "led", "exchange",
})

# Funding-round type suffixes to strip from the end of the prefix so they are
# not mistaken for part of the company name ("Geordie AI Series A" → "Geordie AI").
_ROUND_SUFFIX_RE = re.compile(
    r'\s+(?:series\s+[a-e]|pre-?seed|seed|pre-series\s+a|bridge|angel)'
    r'(?:\s+round|\s+funding)?\s*$',
    re.IGNORECASE,
)

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


# ── company name extraction ───────────────────────────────────────────────────

def extract_company_name(title: str) -> str | None:
    """
    Extract the likely project name from a news headline.

    Splits on the first action verb, then walks backward through the prefix
    collecting capitalised words — stopping at descriptor words ("startup",
    "firm", "infrastructure", etc.) that separate generic context from the name.
    Returns None rather than guessing when no proper noun is found.

    "XYZ Protocol Raises $5M Seed Round"              → "XYZ Protocol"
    "Stablecoin Infrastructure Startup Checker Raises" → "Checker"
    "DeFi Startup ABC Secures Pre-Seed"                → "ABC"
    "Frontera Labs Developer Raises $3M"               → "Frontera Labs"
    "Kalshi valuation hits $22B as prediction market raises $1B" → None
    """
    lower = title.lower()
    verb_pos = len(title)

    for verb in _ACTION_VERBS:
        m = re.search(r'\b' + verb + r'\b', lower)
        if m and m.start() < verb_pos:
            verb_pos = m.start()

    if verb_pos == len(title):
        return None

    prefix = title[:verb_pos]
    # Strip auxiliary verbs that directly precede the action verb ("has raised", etc.)
    prefix = re.sub(r'\s+(?:has|have|had|is|was|were|are)\s*$', '', prefix.strip(), flags=re.IGNORECASE)
    prefix = _ROUND_SUFFIX_RE.sub("", prefix).strip()
    prefix = _NOISE_PREFIX_RE.sub("", prefix).strip()

    words = prefix.split()
    if not words:
        return None

    # Walk backward collecting contiguous proper-noun tokens, capped at 3 words.
    # Stop at: non-capitalised word, descriptor word, or punctuation-only token.
    name_words: list[str] = []
    for w in reversed(words):
        clean = re.sub(r'[^A-Za-z0-9]', '', w)
        if not clean:
            break
        if clean.lower() in _DESCRIPTOR_WORDS:
            break
        if clean[0].isupper() or re.match(r'^[A-Z0-9]+$', clean):
            name_words.insert(0, w)
            if len(name_words) >= 3:
                break
        else:
            break

    if not name_words:
        return None  # no proper noun found — skip rather than guess

    name = " ".join(name_words).strip().strip(",.")
    return name if len(name) >= 2 else None


# ── RSS helpers ───────────────────────────────────────────────────────────────

def fetch_news(query: str, days_back: int = DAYS_BACK) -> list[dict]:
    """Fetch and parse Google News RSS for a query, filtered by recency."""
    params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    url = f"{_RSS_BASE}?{urllib.parse.urlencode(params)}"

    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"  [rss] fetch error for {query!r}: {e}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    try:
        root = ET.fromstring(r.text)
    except ET.ParseError as e:
        print(f"  [rss] parse error for {query!r}: {e}")
        return []

    items = []
    for item in root.iter("item"):
        title_el   = item.find("title")
        link_el    = item.find("link")
        pubdate_el = item.find("pubDate")
        source_el  = item.find("source")

        title   = (title_el.text   or "").strip() if title_el   is not None else ""
        source  = (source_el.text  or "").strip() if source_el  is not None else ""
        pub_raw = (pubdate_el.text or "").strip() if pubdate_el is not None else ""

        # <link> in RSS 2.0 is a bare text node that ET sometimes puts in .tail
        link = ""
        if link_el is not None:
            link = (link_el.text or link_el.tail or "").strip()

        pub_dt = None
        if pub_raw:
            try:
                pub_dt = parsedate_to_datetime(pub_raw)
                if pub_dt < cutoff:
                    continue
            except Exception:
                pass

        company = extract_company_name(title)

        items.append({
            "title":   title,
            "link":    link,
            "source":  source,
            "pub_dt":  pub_dt,
            "company": company,
            "query":   query,
        })

    return items


# ── X-handle resolution (4-layer) ────────────────────────────────────────────

def _extract_handle(text: str) -> str | None:
    for m in _HANDLE_RE.finditer(text):
        h = m.group(1).rstrip("/")
        if h.lower() not in ("status", "share", "intent"):
            return h
    return None


def _layer1_article(url: str) -> str | None:
    """Fetch the news article and look for an X link in the page."""
    if not url:
        return None
    try:
        r = requests.get(url, timeout=10, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        return _extract_handle(r.text)
    except Exception:
        return None



def _layer3_tweet_search(company: str) -> str | None:
    """
    Sorsa tweet search for the company's funding/launch announcement.
    Companies almost always tweet their own raise, so the author of the most
    relevant tweet is likely their account. Name-similarity scoring picks the
    company handle over investors/journalists tweeting about the same news.
    """
    query = (f'"{company}" (raises OR raised OR seed OR launches OR launched) '
             f'-filter:retweets lang:en')
    try:
        tweets = search_tweets(query, order="popular", max_results=20)
    except Exception as e:
        print(f"    [x-search] {company!r}: {e}")
        return None

    candidates: dict[str, int] = {}
    for t in tweets:
        if t.get("is_reply") or t.get("retweeted_status"):
            continue
        user = t.get("user", {})
        username = user.get("screen_name") or user.get("username") or ""
        followers = user.get("followers_count", 0)
        if username and followers >= 100:
            candidates[username] = max(candidates.get(username, 0), followers)

    if not candidates:
        return None

    # Prefer a handle whose text overlaps with the company name
    name_words = [w.lower() for w in company.split()]
    for username in sorted(candidates, key=lambda u: candidates[u], reverse=True):
        if any(w in username.lower() for w in name_words):
            return username

    # Fallback: highest-follower author
    return max(candidates, key=lambda u: candidates[u])


def _layer4_exa_company(company: str) -> str | None:
    """Exa company-category search — find the project website and extract its X link."""
    try:
        res = _get_exa().search(
            f"{company} crypto blockchain official",
            type="auto",
            category="company",
            num_results=5,
            contents={"text": {"max_characters": 1500}},
        )
        for r in res.results:
            text = (getattr(r, "text", "") or "") + " " + r.url
            h = _extract_handle(text)
            if h:
                return h
    except Exception as e:
        print(f"    [exa-co] {company!r}: {e}")
    return None


def resolve_x_handle(company: str, article_url: str = "") -> tuple[str | None, str]:
    """
    Three-layer resolution, cheapest/most direct first:
      1. Fetch news article → extract X link from page text
      2. Sorsa tweet search for funding announcement → author handle
      3. Exa company-category search → X link from company website
    """
    h = _layer1_article(article_url)
    if h:
        return h, "article"

    h = _layer3_tweet_search(company)
    if h:
        return h, "x_tweet"

    h = _layer4_exa_company(company)
    if h:
        return h, "exa_company"

    return None, "not_found"


# ── console output ────────────────────────────────────────────────────────────

def print_article(item: dict, idx: int, handle: str | None = None, source_label: str = ""):
    sep = "─" * 72
    pub = item["pub_dt"].strftime("%Y-%m-%d") if item["pub_dt"] else "unknown"
    print(f"\n{sep}")
    print(f"  #{idx}  {item['title']}")
    print(sep)
    print(f"  Company : {item['company'] or 'n/a'}")
    print(f"  Source  : {item['source']}  |  Published: {pub}")
    print(f"  Query   : {item['query']}")
    if item["link"]:
        print(f"  Link    : {item['link']}")
    if handle:
        print(f"  X       : @{handle}  [{source_label}]")
    elif source_label:
        print(f"  X       : not found")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Google News RSS crypto project search")
    parser.add_argument("--push",    action="store_true", help="Resolve X handles and push to Notion")
    parser.add_argument("--dry-run", action="store_true", help="With --push: resolve handles but skip Notion writes")
    args = parser.parse_args()

    seen_titles:    set[str] = set()
    seen_companies: set[str] = set()
    all_items:      list[dict] = []

    for query in QUERIES:
        print(f"\n{'═' * 72}")
        print(f"  Query: \"{query}\"  (last {DAYS_BACK} days)")
        print(f"{'═' * 72}")

        items = fetch_news(query)
        new_items = []

        for item in items:
            title_key   = item["title"].lower()
            company_key = (item["company"] or "").lower()

            if title_key in seen_titles:
                continue
            if company_key and company_key in seen_companies:
                continue

            seen_titles.add(title_key)
            if company_key:
                seen_companies.add(company_key)
            new_items.append(item)

        if not new_items:
            print("  No new results.")
            continue

        for item in new_items:
            all_items.append(item)
            print_article(item, len(all_items))

    print(f"\n{'═' * 72}")
    print(f"  Found {len(all_items)} unique article(s) across {len(QUERIES)} query(ies).")
    print(f"{'═' * 72}")

    if not args.push:
        print("\n  Tip: run with --push to resolve X handles and sync to Notion.")
        return

    # ── resolve X handles ─────────────────────────────────────────────────────
    print("\nResolving X handles via Exa...")
    for item in all_items:
        company = item.get("company")
        if not company:
            item["_x_handle"] = None
            item["_x_source"] = "no_company"
            continue
        handle, src = resolve_x_handle(company, article_url=item.get("link", ""))
        item["_x_handle"] = handle
        item["_x_source"] = src
        display = f"@{handle}" if handle else "not found"
        print(f"  {company!r:35s} → {display:30s}  [{src}]")
        time.sleep(0.5)

    # ── standard pipeline ─────────────────────────────────────────────────────
    init_db()
    known_ids = get_known_ids()

    accounts: list[dict] = []
    seen_ids:  set[str]  = set()

    print("\nResolving Sorsa user IDs...")
    for item in all_items:
        handle = item.get("_x_handle")
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
            "id":            uid,
            "watchers":      [f"google_news:{item['query']}"],
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
