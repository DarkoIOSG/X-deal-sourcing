"""
Funding enrichment via Surf API.

Fetches funding data for all projects with Recommendation = watch or deep_dive
and writes back to Notion: Raised, Last Round Date, Last Round Amount, Investors.

Run:
  python3 scripts/enrich_funding.py
  python3 scripts/enrich_funding.py --dry-run   # preview without writing
"""

import sys
import argparse
import requests
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config import SURF_API_KEY
from shared.notion import (
    update_row, _DB_URL, _HEADERS, _parse_page,
    PROP_CHECKED_ON_SURF, PROP_RAISED, PROP_LAST_ROUND_DATE,
    PROP_LAST_ROUND_AMOUNT, PROP_LAST_ROUND_VALUATION, PROP_INVESTORS,
)

SURF_URL = "https://api.asksurf.ai/gateway/v1/project/detail"
SURF_FIELDS = "funding"


def fetch_funding(handle: str) -> dict | None:
    """Call Surf API. Returns funding dict or None if not found."""
    clean = handle.lstrip("@")
    r = requests.get(
        SURF_URL,
        headers={"Authorization": f"Bearer {SURF_API_KEY}"},
        params={"handle": clean, "fields": SURF_FIELDS},
        timeout=30,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json().get("data", {}).get("funding")


def parse_funding(funding: dict) -> dict:
    """Extract the fields we care about from the Surf funding response."""
    rounds = funding.get("rounds") or []
    total  = funding.get("total_raise") or 0

    # Most recent round = first in list (Surf returns newest first)
    latest = rounds[0] if rounds else None

    raised = total > 0 or bool(rounds)

    last_date      = None
    last_amount    = None
    last_valuation = None
    investors      = None

    if latest:
        last_date  = latest.get("date")
        amount     = latest.get("amount")
        valuation  = latest.get("valuation")
        round_name = latest.get("round_name", "")

        if amount:
            last_amount = f"${amount/1_000_000:.1f}M {round_name}".strip()
        elif round_name:
            last_amount = round_name

        if valuation:
            last_valuation = f"${valuation/1_000_000:.0f}M"

        investor_names = [
            i["name"] for i in latest.get("investors", []) if i.get("name")
        ]
        if investor_names:
            investors = ", ".join(investor_names)

    return {
        "raised":          raised,
        "last_date":       last_date,
        "last_amount":     last_amount,
        "last_valuation":  last_valuation,
        "investors":       investors,
        "total_raise":     total,
        "num_rounds":      len(rounds),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--handle", type=str, default=None, help="Test a single account e.g. @Outcomexyz")
    args = parser.parse_args()

    print(f"\n=== Funding Enrichment — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")

    import requests as req

    if args.handle:
        handle_clean = args.handle.lstrip("@").lower()
        payload = {
            "filter": {"property": "Username", "rich_text": {"equals": handle_clean}},
            "page_size": 1,
        }
        r = req.post(_DB_URL, headers=_HEADERS, json=payload, timeout=30)
        r.raise_for_status()
        projects = [_parse_page(p) for p in r.json().get("results", [])]
        if not projects:
            print(f"@{handle_clean} not found in Notion.")
            return
        print(f"Testing single project: @{handle_clean}\n")
    else:
        payload = {
            "filter": {
                "and": [
                    {
                        "or": [
                            {"property": "Recommendation", "select": {"equals": "deep_dive"}},
                            {"property": "Recommendation", "select": {"equals": "watch"}},
                        ]
                    },
                    {"property": "Checked On Surf", "checkbox": {"equals": False}},
                ]
            },
            "sorts": [{"property": "Score", "direction": "descending"}],
            "page_size": 100,
        }
        projects = []
        cursor = None
        while True:
            if cursor:
                payload["start_cursor"] = cursor
            r = req.post(_DB_URL, headers=_HEADERS, json=payload, timeout=30)
            r.raise_for_status()
            data = r.json()
            projects.extend(_parse_page(p) for p in data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        print(f"Found {len(projects)} unchecked projects (watch + deep_dive)\n")

    found = not_found = failed = 0

    for p in projects:
        handle    = p.get("username", "")
        notion_id = p["notion_id"]

        print(f"  @{handle:<25}", end=" ", flush=True)

        try:
            funding = fetch_funding(handle)
        except Exception as e:
            print(f"[error] {e}")
            failed += 1
            time.sleep(1)
            continue

        if funding is None:
            print("[not found in Surf]")
            if not args.dry_run:
                update_row(notion_id, {PROP_CHECKED_ON_SURF: True})
            not_found += 1
            time.sleep(0.5)
            continue

        parsed = parse_funding(funding)
        print(
            f"raised={parsed['raised']}  "
            f"rounds={parsed['num_rounds']}  "
            f"total=${parsed['total_raise']/1_000_000:.1f}M  "
            f"latest={parsed['last_amount'] or 'n/a'}"
        )

        if not args.dry_run:
            fields = {
                PROP_CHECKED_ON_SURF: True,
                PROP_RAISED:          parsed["raised"],
            }
            if parsed["last_date"]:
                fields[PROP_LAST_ROUND_DATE] = parsed["last_date"]
            if parsed["last_amount"]:
                fields[PROP_LAST_ROUND_AMOUNT] = parsed["last_amount"]
            if parsed["last_valuation"]:
                fields[PROP_LAST_ROUND_VALUATION] = parsed["last_valuation"]
            if parsed["investors"]:
                fields[PROP_INVESTORS] = parsed["investors"]
            try:
                update_row(notion_id, fields)
            except Exception as e:
                print(f"\n  [notion error] @{handle}: {e}")
                failed += 1
                time.sleep(1)
                continue

        found += 1
        time.sleep(0.5)

    sep = "─" * 55
    print(f"\n{sep}")
    print(f"  Done. {found} enriched, {not_found} not in Surf, {failed} errors.")
    if args.dry_run:
        print("  [dry-run] No changes written to Notion.")
    print(sep)


if __name__ == "__main__":
    main()
