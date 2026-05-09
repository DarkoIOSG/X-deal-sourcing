"""
Deep-dive pipeline — Phase 3

Pulls all Notion rows with Status=Scored + Recommendation=deep_dive,
runs the deep-dive agent on each, and writes the memo + status back to Notion.

Run:
  python deep_dive_run.py [--limit N]

Flags:
  --limit N   Only process the top-N candidates (by score). Default: all.
  --dry-run   Print candidates but do not call the agent.
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

from shared.notion import (
    query_candidates, update_row,
    PROP_MEMO, PROP_STATUS, PROP_LAST_TOUCHED,
)
from deep_dive.agent import deep_dive_and_log

THESIS_PATH = Path("shared/prompts/thesis_doc.md")


def _project_from_notion(page: dict) -> dict:
    """Convert a shared/notion page dict to the shape deep_dive expects."""
    return {
        "handle": f"@{page['username']}",
        "description": page.get("one_liner") or page.get("bio") or "(none)",
        "categories": page.get("sectors") or [],
        "tweets": [],  # deep_dive agent fetches fresh data via web_search
    }


def main():
    parser = argparse.ArgumentParser(description="Run deep-dive agent on scored candidates")
    parser.add_argument("--limit", type=int, default=None, help="Max candidates to process")
    parser.add_argument("--dry-run", action="store_true", help="List candidates without running agent")
    args = parser.parse_args()

    print(f"\n=== Deep-Dive Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")

    thesis = THESIS_PATH.read_text()

    candidates = query_candidates(status="Scored", recommendation="deep_dive")
    if args.limit:
        candidates = candidates[: args.limit]

    print(f"Found {len(candidates)} deep_dive candidate(s)\n")
    if not candidates:
        print("No candidates. Run score_run.py first.")
        return

    sep = "─" * 65
    print(sep)
    for i, p in enumerate(candidates, 1):
        score = p.get("score") or "?"
        print(f"  {i:2d}. [{score:>3}] @{p['username']}  —  {(p.get('one_liner') or '')[:55]}")
    print(sep)

    if args.dry_run:
        print("\n[dry-run] Stopping before agent calls.")
        return

    print()
    today = datetime.today().strftime("%Y-%m-%d")
    done, failed = 0, 0

    for page in candidates:
        handle = f"@{page['username']}"
        notion_id = page["notion_id"]
        scoring_json = page.get("scoring_json") or {}

        print(f"\n{'─'*65}")
        print(f"  Running deep dive: {handle}")
        print(f"{'─'*65}")

        try:
            project = _project_from_notion(page)
            memo = deep_dive_and_log(project, thesis, scoring_json)

            update_row(notion_id, {
                PROP_MEMO:         memo,
                PROP_STATUS:       "Deep_Dived",
                PROP_LAST_TOUCHED: today,
            })

            print(f"  [ok] Memo written to Notion — {handle}")
            done += 1

        except Exception as e:
            print(f"  [error] {handle}: {e}")
            failed += 1

        time.sleep(1)

    print(f"\n{sep}")
    print(f"  Done. {done} memo(s) written, {failed} error(s).")
    print(f"  Status set to Deep_Dived in Notion.")
    print(sep)


if __name__ == "__main__":
    main()
