"""
Find senior people on X for all founder_watchlist.txt company sections.
Usage: python3 scripts/find_watchlist_handles.py [company_slug]
Outputs grouped handles ready to paste into founder_watchlist.txt.
"""

import sys
import re
import time
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from api.sorsa import search_tweets

# ── config ────────────────────────────────────────────────────────────────────

SENIOR_TITLES = re.compile(
    r'\b(co-?founder|ceo|cto|coo|cpo|cso|vp\b|vice president|'
    r'head of|director|president|principal|general counsel|chief\b|'
    r'engineer|researcher|protocol|scientist|partner\b)',
    re.IGNORECASE,
)

# Each entry: (section_header, bio_keywords, search_terms)
COMPANIES = [
    (
        "dYdX",
        ["dydx"],
        ["dYdX co-founder", "dYdX CEO", "dYdX CTO", "dYdX \"head of\"",
         "dYdX director", "dYdX chief", "dYdX engineer", "dYdX research"],
    ),
    (
        "Aave / MakerDAO",
        ["aave", "makerDAO", "makerdao", "sky protocol"],
        ["Aave co-founder", "Aave CEO", "Aave \"head of\"", "Aave director",
         "MakerDAO co-founder", "MakerDAO CEO", "MakerDAO \"head of\"", "MakerDAO director"],
    ),
    (
        "Solana Labs",
        ["solana labs", "solana foundation"],
        ["\"Solana Labs\" co-founder", "\"Solana Labs\" CEO", "\"Solana Labs\" CTO",
         "\"Solana Labs\" \"head of\"", "\"Solana Labs\" engineer",
         "\"Solana Foundation\" director", "\"Solana Foundation\" \"head of\""],
    ),
    (
        "Ethereum Foundation",
        ["ethereum foundation"],
        ["\"Ethereum Foundation\" researcher", "\"Ethereum Foundation\" director",
         "\"Ethereum Foundation\" engineer", "\"Ethereum Foundation\" \"head of\"",
         "\"Ethereum Foundation\" co-founder"],
    ),
    (
        "Optimism",
        ["optimism", "op labs"],
        ["Optimism co-founder", "Optimism CEO", "Optimism \"head of\"",
         "\"OP Labs\" engineer", "\"OP Labs\" director", "Optimism researcher"],
    ),
    (
        "Arbitrum / Offchain Labs",
        ["arbitrum", "offchain labs"],
        ["Arbitrum co-founder", "Arbitrum CEO", "\"Offchain Labs\" \"head of\"",
         "\"Offchain Labs\" engineer", "Arbitrum director"],
    ),
    (
        "StarkWare / Matter Labs",
        ["starkware", "matter labs", "starknet"],
        ["StarkWare co-founder", "StarkWare CEO", "StarkWare \"head of\"",
         "\"Matter Labs\" co-founder", "\"Matter Labs\" CEO", "\"Matter Labs\" engineer"],
    ),
    (
        "Chainlink",
        ["chainlink"],
        ["Chainlink co-founder", "Chainlink CEO", "Chainlink \"head of\"",
         "Chainlink director", "Chainlink chief", "Chainlink researcher"],
    ),
    (
        "LayerZero",
        ["layerzero"],
        ["LayerZero co-founder", "LayerZero CEO", "LayerZero \"head of\"",
         "LayerZero director", "LayerZero engineer"],
    ),
    (
        "EigenLayer",
        ["eigenlayer", "eigen labs"],
        ["EigenLayer co-founder", "EigenLayer CEO", "EigenLayer \"head of\"",
         "\"Eigen Labs\" engineer", "EigenLayer researcher"],
    ),
    (
        "Binance",
        ["binance"],
        ["Binance co-founder", "Binance CEO", "Binance CTO", "Binance \"head of\"",
         "Binance director", "Binance chief", "Binance VP"],
    ),
    (
        "OKX",
        ["okx", "okex"],
        ["OKX co-founder", "OKX CEO", "OKX \"head of\"", "OKX director", "OKX chief"],
    ),
    (
        "Kraken",
        ["kraken"],
        ["Kraken co-founder", "Kraken CEO", "Kraken \"head of\"",
         "Kraken director", "Kraken chief", "Kraken VP"],
    ),
    (
        "Circle",
        ["circle"],
        ["Circle co-founder", "Circle CEO", "Circle CTO", "Circle \"head of\"",
         "Circle director", "Circle chief", "Circle VP"],
    ),
    (
        "Fireblocks",
        ["fireblocks"],
        ["Fireblocks co-founder", "Fireblocks CEO", "Fireblocks \"head of\"",
         "Fireblocks director", "Fireblocks chief"],
    ),
    (
        "Paxos",
        ["paxos"],
        ["Paxos co-founder", "Paxos CEO", "Paxos \"head of\"",
         "Paxos director", "Paxos chief"],
    ),
    (
        "a16z Crypto / Paradigm alumni",
        ["a16z crypto", "paradigm", "andreessen horowitz crypto"],
        ["\"a16z crypto\" partner", "\"a16z crypto\" \"general partner\"",
         "Paradigm co-founder", "Paradigm partner", "Paradigm researcher",
         "\"a16z\" crypto partner"],
    ),
]

# ── search ────────────────────────────────────────────────────────────────────

def search_company(section: str, bio_keywords: list[str], queries: list[str]) -> list[tuple]:
    found: dict[str, dict] = {}
    skip_handles = set(bio_keywords)  # skip official accounts that match bio

    for query in queries:
        print(f"    {query!r}", file=sys.stderr, flush=True)
        try:
            tweets = search_tweets(query, order="popular", max_results=100)
        except Exception as e:
            print(f"      [warn] {e}", file=sys.stderr)
            time.sleep(2)
            continue

        for t in tweets:
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

            if not any(kw in bio_lower for kw in bio_keywords):
                continue

            if not SENIOR_TITLES.search(bio):
                continue

            if handle.lower() in skip_handles:
                continue

            if handle not in found or followers > found[handle]["followers"]:
                found[handle] = {"name": name, "bio": bio, "followers": followers}

        time.sleep(0.4)

    return sorted(found.items(), key=lambda x: x[1]["followers"], reverse=True)


# ── main ──────────────────────────────────────────────────────────────────────

filter_slug = sys.argv[1].lower() if len(sys.argv) > 1 else None

results_by_section: dict[str, list] = {}

for section, bio_keywords, queries in COMPANIES:
    if filter_slug and filter_slug not in section.lower():
        continue
    print(f"\n[{section}]", file=sys.stderr, flush=True)
    ranked = search_company(section, bio_keywords, queries)
    results_by_section[section] = ranked
    print(f"  → {len(ranked)} found", file=sys.stderr, flush=True)

# ── output ────────────────────────────────────────────────────────────────────

print("\n\n" + "═" * 72)
print("  HANDLES — paste into founder_watchlist.txt")
print("═" * 72)

for section, ranked in results_by_section.items():
    bar = "─" * (68 - len(section))
    print(f"\n# ── {section} {bar}")
    if not ranked:
        print("# (no results)")
    for handle, info in ranked:
        print(f"@{handle}")

print("\n\n" + "═" * 72)
print("  WITH BIOS")
print("═" * 72)

for section, ranked in results_by_section.items():
    bar = "─" * (68 - len(section))
    print(f"\n# ── {section} {bar}")
    for handle, info in ranked:
        print(f"  @{handle:28s}  {info['followers']:>8,}  |  {info['bio'][:90]}")
