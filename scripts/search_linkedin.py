"""
LinkedIn search — find early-stage crypto/DeFi projects via Exa-indexed posts.

Exa indexes LinkedIn Pulse articles and posts. LinkedIn is a distinct signal:
founder-authored announcements often appear here before or alongside news coverage.

LinkedIn's login wall truncates post text, so company extraction relies on the
article/post title and the URL slug, not the body text.

Run:
  python3 scripts/search_linkedin.py                  # print results only
  python3 scripts/search_linkedin.py --push           # resolve handles + push to Notion
  python3 scripts/search_linkedin.py --push --dry-run # resolve handles, skip Notion writes
"""

import re
import sys
import time
import argparse
from datetime import datetime, timedelta, timezone
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

DAYS_BACK   = 14
NUM_RESULTS = 10  # Exa results per query

QUERIES = [
    # company-first patterns (best for title extraction)
    '"seed round" defi crypto raised million',
    '"seed round" web3 startup raised',
    '"pre-seed" crypto blockchain raised',
    '"raised" million stablecoin startup',
    '"raised" million "prediction market" crypto',
    '"raised" million perpetuals dex',
    '"raised" million "onchain payments"',
    '"raised" million "rwa tokenization"',
    '"raised" million "ai agent" defi',
    # founder-announcement style (LinkedIn-native phrasing)
    '"excited to announce" defi crypto raised seed',
    '"thrilled to share" blockchain seed round',
    '"proud to announce" crypto defi raised',
    # launch signals
    '"launched" defi protocol crypto',
    '"announcing" stablecoin crypto startup',
]

_RSS_BASE = "https://news.google.com/rss/search"

# ── name extraction helpers ───────────────────────────────────────────────────

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
    # investor-first patterns common on LinkedIn
    "invests", "invested",
    "backs", "closes",
    "leads", "led",
)

_NOISE_PREFIX_RE = re.compile(
    r'^(?:new\s+|the\s+|exclusive[:\s]+|breaking[:\s]+|report[:\s]+|'
    r'(?:blockchain|defi|crypto|web3|nft|fintech|onchain)\s+startup\s+)',
    re.IGNORECASE,
)

_DESCRIPTOR_WORDS = frozenset({
    "startup", "firm", "company", "developer", "infrastructure",
    "builder", "provider", "venture", "unit", "arm", "division",
    "backed", "funded", "led", "exchange",
})

_ROUND_SUFFIX_RE = re.compile(
    r'\s+(?:series\s+[a-e]|pre-?seed|seed|pre-series\s+a|bridge|angel)'
    r'(?:\s+round|\s+funding)?\s*$',
    re.IGNORECASE,
)

# "Name on LinkedIn: 'post text...'" → strip the preamble
_LINKEDIN_POST_PREFIX_RE = re.compile(
    r'^.+?\bon\s+LinkedIn\b\s*[:\|]\s*["“]?',
    re.IGNORECASE,
)

# linkedin.com/company/slug → slug
_COMPANY_SLUG_RE = re.compile(r'linkedin\.com/company/([a-z0-9][a-z0-9-]*)', re.IGNORECASE)

# linkedin.com/pulse/slug-with-hyphens-HASH → slug (strip trailing hash-like suffix)
_PULSE_SLUG_RE = re.compile(r'linkedin\.com/pulse/(.+?)(?:-[a-z0-9]{4,})?/?$', re.IGNORECASE)

# "Introducing Kairos", "Launching X", "Meet X" — verb-first patterns where company follows the verb
# (?i:...) applies IGNORECASE only to the verb group, keeping the capture group case-sensitive
_INTRO_VERB_RE = re.compile(
    r'(?i:\b(?:introducing|launching|meet|unveiling|presenting))\s+'
    r'([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,2})',
)

# "Clouted's $7M seed" — single-word possessive immediately before a funding signal
# Single-word only to avoid grabbing preceding words like "Announcing Clouted's"
_POSSESSIVE_FUND_RE = re.compile(
    r'\b([A-Z][a-zA-Z0-9]+)'
    r"'s\s+(?:\$\d|\d+\s*[mk]\b|seed|series|pre-?seed|round|funding)",
    re.IGNORECASE,
)

# "doing at Polsia", "built at X" — company name follows "at"
_AT_COMPANY_RE = re.compile(r'\bat\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)\b')


def extract_company_name(title: str) -> str | None:
    """Extract project name from a headline or post title via action-verb splitting."""
    lower = title.lower()
    verb_pos = len(title)

    for verb in _ACTION_VERBS:
        m = re.search(r'\b' + verb + r'\b', lower)
        if m and m.start() < verb_pos:
            verb_pos = m.start()

    if verb_pos == len(title):
        return None

    prefix = title[:verb_pos]
    prefix = re.sub(r'\s+(?:has|have|had|is|was|were|are)\s*$', '', prefix.strip(), flags=re.IGNORECASE)
    prefix = _ROUND_SUFFIX_RE.sub("", prefix).strip()
    prefix = _NOISE_PREFIX_RE.sub("", prefix).strip()

    words = prefix.split()
    if not words:
        return None

    name_words: list[str] = []
    for w in reversed(words):
        clean = re.sub(r'[^A-Za-z0-9]', '', w)
        if not clean:
            break
        if re.match(r'^\d', clean):  # number or money token ($5M, 30M, 100)
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
        return None

    name = " ".join(name_words).strip().strip(",.")
    return name if len(name) >= 2 else None


def _slug_to_title(slug: str) -> str:
    """Convert a URL slug to a title-cased string for name extraction."""
    return " ".join(w.capitalize() for w in slug.replace("-", " ").split())


def extract_company_from_result(title: str, url: str) -> str | None:
    """
    Extract company name from a LinkedIn Exa result.
    Priority:
      1. Title after stripping "Name on LinkedIn: " post prefix
      2. Raw title (works for Pulse article titles)
      3. Company page URL slug  (linkedin.com/company/slug)
      4. Pulse URL slug converted to title case
    """
    # 1. Strip LinkedIn post preamble and try
    if title:
        clean = _LINKEDIN_POST_PREFIX_RE.sub("", title).strip().strip('"“”')
        name = extract_company_name(clean)
        if name:
            return name

        # 2. Raw title (Pulse articles have proper headlines)
        name = extract_company_name(title)
        if name:
            return name

    # 3. LinkedIn-specific title patterns (post titles don't follow news-headline structure)

    # "Introducing Kairos, the future of..." — verb-first, company follows
    m = _INTRO_VERB_RE.search(title)
    if m:
        name = m.group(1).strip().rstrip(",.:!")
        if len(name) >= 2:
            return name

    # "Clouted's $7M seed" — possessive before funding signal
    m = _POSSESSIVE_FUND_RE.search(title)
    if m:
        name = m.group(1).strip()
        if len(name) >= 2:
            return name

    # "doing at Polsia is the boldest proof" — company after "at"
    for m in _AT_COMPANY_RE.finditer(title):
        name = m.group(1).strip()
        if len(name) >= 2 and name.lower() not in _DESCRIPTOR_WORDS:
            return name

    # 4. Company page URL: linkedin.com/company/frontera-labs
    m = _COMPANY_SLUG_RE.search(url)
    if m:
        name = _slug_to_title(m.group(1))
        return name if len(name) >= 2 else None

    # 5. Pulse URL slug as last resort
    m = _PULSE_SLUG_RE.search(url)
    if m:
        slug_title = _slug_to_title(m.group(1))
        name = extract_company_name(slug_title)
        if name:
            return name

    return None


# ── Exa fetch ─────────────────────────────────────────────────────────────────

_exa: Exa | None = None


def _get_exa() -> Exa:
    global _exa
    if _exa is None:
        _exa = Exa(api_key=EXA_API_KEY)
    return _exa


def fetch_linkedin_results(query: str, days_back: int = DAYS_BACK) -> list[dict]:
    """Query Exa restricted to linkedin.com, return items filtered by recency."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    try:
        res = _get_exa().search(
            query,
            type="neural",
            num_results=NUM_RESULTS,
            include_domains=["linkedin.com"],
            contents={"text": {"max_characters": 500}},
        )
    except Exception as e:
        print(f"  [exa] fetch error for {query!r}: {e}")
        return []

    items = []
    for r in res.results:
        title    = (getattr(r, "title", "") or "").strip()
        pub_raw  = getattr(r, "published_date", None)

        pub_dt = None
        if pub_raw:
            try:
                pub_dt = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
                if pub_dt < cutoff:
                    continue
            except Exception:
                pass

        company = extract_company_from_result(title, r.url)

        items.append({
            "title":   title,
            "url":     r.url,
            "pub_dt":  pub_dt,
            "company": company,
            "query":   query,
        })

    return items


# ── X-handle resolution (4-layer) ────────────────────────────────────────────

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


def _layer1_article(url: str) -> str | None:
    if not url:
        return None
    try:
        r = requests.get(url, timeout=10, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        return _extract_handle(r.text)
    except Exception:
        return None



def _layer3_tweet_search(company: str) -> str | None:
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

    name_words = [w.lower() for w in company.split()]
    for username in sorted(candidates, key=lambda u: candidates[u], reverse=True):
        if any(w in username.lower() for w in name_words):
            return username

    return max(candidates, key=lambda u: candidates[u])


def _layer4_exa_company(company: str) -> str | None:
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
      1. Fetch LinkedIn page → extract X link (rarely present due to login wall)
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

def print_item(item: dict, idx: int, handle: str | None = None, source_label: str = ""):
    sep = "─" * 72
    pub = item["pub_dt"].strftime("%Y-%m-%d") if item["pub_dt"] else "unknown"
    print(f"\n{sep}")
    print(f"  #{idx}  {item['title']}")
    print(sep)
    print(f"  Company : {item['company'] or 'n/a'}")
    print(f"  Published: {pub}")
    print(f"  Query   : {item['query']}")
    print(f"  URL     : {item['url']}")
    if handle:
        print(f"  X       : @{handle}  [{source_label}]")
    elif source_label:
        print(f"  X       : not found")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LinkedIn crypto project search via Exa")
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

        items = fetch_linkedin_results(query)
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
            print_item(item, len(all_items))

        time.sleep(0.5)  # respect Exa rate limits

    print(f"\n{'═' * 72}")
    print(f"  Found {len(all_items)} unique result(s) across {len(QUERIES)} query(ies).")
    print(f"{'═' * 72}")

    if not args.push:
        print("\n  Tip: run with --push to resolve X handles and sync to Notion.")
        return

    # ── resolve X handles ─────────────────────────────────────────────────────
    print("\nResolving X handles...")
    for item in all_items:
        company = item.get("company")
        if not company:
            item["_x_handle"] = None
            item["_x_source"] = "no_company"
            continue
        handle, src = resolve_x_handle(company, article_url=item.get("url", ""))
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
            "watchers":      [f"linkedin:{item['query']}"],
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
