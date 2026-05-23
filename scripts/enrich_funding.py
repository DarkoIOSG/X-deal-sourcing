"""
Funding enrichment — DeFiLlama first, Surf fallback.

For each project with Recommendation = watch or deep_dive:
  1. Try to match by name against the full DeFiLlama raises dataset (one API call upfront)
  2. If no match → call Surf API by Twitter handle
  3. Write results back to Notion

Notion fields updated: Raised, Last Round Date, Last Round Amount,
Last Round Valuation, Investors, Checked Fundraising.

Run:
  python3 scripts/enrich_funding.py
  python3 scripts/enrich_funding.py --dry-run        # preview without writing
  python3 scripts/enrich_funding.py --handle @yield  # test a single account
"""

import sys
import argparse
import requests
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(override=True)

from config import SURF_API_KEY, DEFILLAMA_API_KEY
from shared.notion import (
    update_row, _DB_URL, _HEADERS, _parse_page,
    PROP_CHECKED_ON_SURF, PROP_RAISED, PROP_LAST_ROUND_DATE,
    PROP_LAST_ROUND_AMOUNT, PROP_LAST_ROUND_VALUATION, PROP_INVESTORS,
)

SURF_URL    = "https://api.asksurf.ai/gateway/v1/project/detail"
SURF_FIELDS = "funding"
DEFILLAMA_RAISES_URL = f"https://pro-api.llama.fi/{DEFILLAMA_API_KEY}/api/raises"


# ── DeFiLlama ─────────────────────────────────────────────────────────────────

def _fmt_amount(amount, round_name: str) -> str:
    """Format a DeFiLlama amount (already in $M) into a readable string."""
    if amount is None:
        return round_name or "Unknown"
    try:
        amt = float(amount)
        label = f"${amt / 1000:.1f}B" if amt >= 1000 else f"${amt:.1f}M"
        return f"{label} {round_name}".strip()
    except (TypeError, ValueError):
        return f"${amount}M {round_name}".strip()


def fetch_defillama_index() -> dict[str, dict]:
    """
    Fetch all raises from DeFiLlama Pro and return a dict keyed by
    lowercase project name. When a project has multiple rounds, we keep
    the most recent one and sum the amounts for total_raise.
    """
    print("Fetching DeFiLlama raises...", end=" ", flush=True)
    try:
        r = requests.get(DEFILLAMA_RAISES_URL, timeout=30)
        r.raise_for_status()
        raises = r.json().get("raises", [])
    except Exception as e:
        print(f"[error: {e}] — will use Surf only")
        return {}

    # Group rounds by project name, keep most recent as primary
    index: dict[str, dict] = {}
    totals: dict[str, float] = {}

    for raise_ in raises:
        name = (raise_.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        amount = raise_.get("amount") or 0

        totals[key] = totals.get(key, 0) + float(amount)

        existing = index.get(key)
        if existing is None or raise_["date"] > existing["date"]:
            index[key] = raise_

    # Attach total_raise to each entry
    for key, raise_ in index.items():
        raise_["_total_raise"] = totals[key]

    print(f"{len(raises)} raises → {len(index)} unique projects")
    return index


def parse_defillama(raise_: dict) -> dict:
    """Convert a DeFiLlama raise entry into the same shape as parse_surf()."""
    amount     = raise_.get("amount")
    round_name = raise_.get("round", "")
    date_ts    = raise_.get("date")
    valuation  = raise_.get("valuation")
    leads      = raise_.get("leadInvestors") or []
    others     = raise_.get("otherInvestors") or []
    total      = raise_.get("_total_raise", float(amount) if amount else 0)

    last_amount = _fmt_amount(amount, round_name) if (amount or round_name) else None
    last_date   = (datetime.fromtimestamp(date_ts, tz=timezone.utc).strftime("%Y-%m-%d")
                   if date_ts else None)
    last_val    = _fmt_amount(float(valuation), "").strip() if valuation else None
    investors   = ", ".join(leads + others) or None

    return {
        "raised":        True,
        "last_date":     last_date,
        "last_amount":   last_amount,
        "last_valuation": last_val,
        "investors":     investors,
        "total_raise":   total,
        "source":        "defillama",
    }


def match_defillama(project: dict, index: dict[str, dict]) -> dict | None:
    """
    Try to match a Notion project against the DeFiLlama index.
    Attempts: exact name → display name without common suffixes.
    Returns the parsed funding dict or None.
    """
    candidates = []
    name = (project.get("name") or "").strip().lower()
    if name:
        candidates.append(name)
        # strip common suffixes to widen the match
        for suffix in (" protocol", " finance", " network", " labs", " dao", " fi"):
            if name.endswith(suffix):
                candidates.append(name[: -len(suffix)].strip())

    for candidate in candidates:
        if candidate in index:
            return parse_defillama(index[candidate])
    return None


# ── Surf ──────────────────────────────────────────────────────────────────────

def fetch_surf(handle: str) -> dict | None:
    """Call Surf API. Returns raw funding dict or None if not found."""
    r = requests.get(
        SURF_URL,
        headers={"Authorization": f"Bearer {SURF_API_KEY}"},
        params={"handle": handle.lstrip("@"), "fields": SURF_FIELDS},
        timeout=30,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json().get("data", {}).get("funding")


def parse_surf(funding: dict) -> dict:
    """Extract fields from the Surf funding response."""
    rounds = funding.get("rounds") or []
    total  = funding.get("total_raise") or 0
    latest = rounds[0] if rounds else None

    last_date = last_amount = last_valuation = investors = None

    if latest:
        last_date  = latest.get("date")
        amount     = latest.get("amount")
        valuation  = latest.get("valuation")
        round_name = latest.get("round_name", "")

        if amount:
            last_amount = f"${amount / 1_000_000:.1f}M {round_name}".strip()
        elif round_name:
            last_amount = round_name

        if valuation:
            last_valuation = f"${valuation / 1_000_000:.0f}M"

        names = [i["name"] for i in latest.get("investors", []) if i.get("name")]
        investors = ", ".join(names) or None

    return {
        "raised":        total > 0 or bool(rounds),
        "last_date":     last_date,
        "last_amount":   last_amount,
        "last_valuation": last_valuation,
        "investors":     investors,
        "total_raise":   total,
        "source":        "surf",
    }


# ── Notion write ──────────────────────────────────────────────────────────────

def write_funding(notion_id: str, parsed: dict):
    fields = {PROP_CHECKED_ON_SURF: True, PROP_RAISED: parsed["raised"]}
    if parsed["last_date"]:
        fields[PROP_LAST_ROUND_DATE] = parsed["last_date"]
    if parsed["last_amount"]:
        fields[PROP_LAST_ROUND_AMOUNT] = parsed["last_amount"]
    if parsed["last_valuation"]:
        fields[PROP_LAST_ROUND_VALUATION] = parsed["last_valuation"]
    if parsed["investors"]:
        fields[PROP_INVESTORS] = parsed["investors"]
    update_row(notion_id, fields)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--handle", default=None, help="Test a single account e.g. @yield_xyz")
    args = parser.parse_args()

    print(f"\n=== Funding Enrichment — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")

    # Load DeFiLlama data once upfront
    defillama_index = fetch_defillama_index()
    print()

    # Query Notion
    if args.handle:
        handle_clean = args.handle.lstrip("@").lower()
        payload = {
            "filter": {"property": "Username", "rich_text": {"equals": handle_clean}},
            "page_size": 1,
        }
        r = requests.post(_DB_URL, headers=_HEADERS, json=payload, timeout=30)
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
                    {"property": "Checked Fundraising", "checkbox": {"equals": False}},
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
            r = requests.post(_DB_URL, headers=_HEADERS, json=payload, timeout=30)
            r.raise_for_status()
            data = r.json()
            projects.extend(_parse_page(p) for p in data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        print(f"Found {len(projects)} unchecked projects (watch + deep_dive)\n")

    from_defillama = from_surf = not_found = failed = 0

    for p in projects:
        handle    = p.get("username", "")
        notion_id = p["notion_id"]

        print(f"  @{handle:<25}", end=" ", flush=True)

        # 1. Try DeFiLlama first
        parsed = match_defillama(p, defillama_index)
        if parsed:
            print(
                f"[defillama] raised=True  "
                f"latest={parsed['last_amount'] or 'n/a'}  "
                f"investors={parsed['investors'] or '—'}"
            )
            if not args.dry_run:
                try:
                    write_funding(notion_id, parsed)
                except Exception as e:
                    print(f"\n  [notion error] @{handle}: {e}")
                    failed += 1
                    continue
            from_defillama += 1
            time.sleep(0.3)
            continue

        # 2. Fall back to Surf
        if not handle:
            print("[no handle — skipping Surf]")
            not_found += 1
            continue

        try:
            funding = fetch_surf(handle)
        except Exception as e:
            print(f"[surf error] {e}")
            failed += 1
            time.sleep(1)
            continue

        if funding is None:
            print("[not found in DeFiLlama or Surf]")
            if not args.dry_run:
                update_row(notion_id, {PROP_CHECKED_ON_SURF: True})
            not_found += 1
            time.sleep(0.5)
            continue

        parsed = parse_surf(funding)
        print(
            f"[surf]      raised={parsed['raised']}  "
            f"latest={parsed['last_amount'] or 'n/a'}"
        )

        if not args.dry_run:
            try:
                write_funding(notion_id, parsed)
            except Exception as e:
                print(f"\n  [notion error] @{handle}: {e}")
                failed += 1
                time.sleep(1)
                continue

        from_surf += 1
        time.sleep(0.5)

    sep = "─" * 55
    print(f"\n{sep}")
    print(f"  DeFiLlama: {from_defillama}  |  Surf: {from_surf}  |  Not found: {not_found}  |  Errors: {failed}")
    if args.dry_run:
        print("  [dry-run] No changes written to Notion.")
    print(sep)


if __name__ == "__main__":
    main()
