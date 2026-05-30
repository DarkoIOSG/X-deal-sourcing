"""
Quick test: dump raw Exa output for a company name search.

Usage:
  python3 scripts/test_exa.py "Hypernova"
  python3 scripts/test_exa.py "Hypernova" --neural   # use type=neural instead of auto
"""

import re
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from exa_py import Exa
from config import EXA_API_KEY

_HANDLE_RE = re.compile(
    r'(?:twitter|x)\.com/'
    r'(?!share|intent|home|search|hashtag|status|i/|messages|explore|notifications|settings|'
    r'privacy|tos|about|help|download|login|signup|compose)'
    r'([A-Za-z0-9_]{1,50})',
    re.IGNORECASE,
)


def extract_handles(text: str) -> list[str]:
    return [m.group(1) for m in _HANDLE_RE.finditer(text)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("company", help="Company name to search")
    parser.add_argument("--neural", action="store_true", help="Use type=neural instead of auto")
    parser.add_argument("--num", type=int, default=5, help="Number of results (default 5)")
    args = parser.parse_args()

    query = f"{args.company} crypto blockchain official"
    search_type = "neural" if args.neural else "auto"

    print(f"Query   : {query!r}")
    print(f"Type    : {search_type}  |  category=company  |  num={args.num}")
    print("─" * 72)

    exa = Exa(api_key=EXA_API_KEY)
    res = exa.search(
        query,
        type=search_type,
        category="company",
        num_results=args.num,
        contents={"text": {"max_characters": 1500}},
    )

    if not res.results:
        print("No results.")
        return

    found_handle = None
    for i, r in enumerate(res.results, 1):
        text = (getattr(r, "text", "") or "")
        combined = text + " " + r.url
        handles = extract_handles(combined)

        print(f"\n#{i}  {r.url}")
        if getattr(r, "title", None):
            print(f"    Title   : {r.title}")
        if text:
            preview = text[:300].replace("\n", " ")
            print(f"    Text    : {preview}...")
        if handles:
            print(f"    Handles : {handles}")
            if found_handle is None:
                found_handle = handles[0]
        else:
            print(f"    Handles : (none found)")

    print("\n" + "─" * 72)
    if found_handle:
        print(f"Result  : @{found_handle}  (first handle from first matching result)")
    else:
        print("Result  : not found")


if __name__ == "__main__":
    main()
