"""
Scoring pipeline — Phase 1 + Phase 2

Phase 1: pull all Status=New pages from Notion, hard-filter by type / tweet
         freshness / active-thesis sector overlap.
Phase 2: score survivors with Claude Haiku against thesis.md, write results
         back to Notion (Score, Recommendation, Scoring_JSON, Processed_At,
         Status → Scored).

Run:
  python score_run.py
"""

import time
from datetime import datetime
from tqdm import tqdm

from api.notion import query_new_accounts, update_scoring, update_filtered
from api.sorsa import get_user_tweets
from pipeline.score_filter import filter_candidates, EXCLUDED_SECTORS
from pipeline.score import score_project


def main():
    print(f"\n=== Scoring Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    print(f"Excluded sectors: {', '.join(sorted(EXCLUDED_SECTORS))}\n")

    # ── Phase 1: pull & filter ─────────────────────────────────────────────────
    print("Querying Notion for unprocessed accounts...")
    pages = query_new_accounts()
    print(f"Found {len(pages)} account(s) with Status = New\n")

    if not pages:
        print("Nothing to score. Run the main pipeline first to populate Notion.")
        return

    candidates, dropped = filter_candidates(pages)

    print(f"Phase 1 results: {len(candidates)} candidate(s), {len(dropped)} dropped")
    if dropped:
        reason_counts: dict[str, int] = {}
        for _, reason in dropped:
            key = reason.split(":")[0]
            reason_counts[key] = reason_counts.get(key, 0) + 1
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            print(f"  {count:3d}  {reason}")

        print("  Marking dropped projects in Notion...")
        for page, reason in dropped:
            try:
                update_filtered(page["page_id"], reason)
            except Exception as e:
                print(f"  [warn] could not mark @{page.get('username', '?')}: {e}")
    print()

    if not candidates:
        print("No candidates passed Phase 1 filters.")
        return

    # ── Phase 2: score ─────────────────────────────────────────────────────────
    print(f"Phase 2: scoring {len(candidates)} candidate(s) against thesis...\n")

    scored: list[tuple[dict, dict]] = []
    for page in tqdm(candidates, desc="Scoring"):
        try:
            tweets: list[str] = []
            if page.get("account_id"):
                raw = get_user_tweets(page["account_id"], max_tweets=20)
                tweets = [t.get("full_text", "") for t in raw if t.get("full_text")]

            result = score_project(page, tweets)
            update_scoring(page["page_id"], result)
            scored.append((page, result))
        except Exception as e:
            print(f"\n  [warn] @{page.get('username', '?')}: {e}")
        time.sleep(0.3)

    # ── Summary ────────────────────────────────────────────────────────────────
    scored.sort(key=lambda x: x[1].get("thesis_fit_score", 0), reverse=True)

    deep_dives = [(p, r) for p, r in scored if r.get("recommendation") == "deep_dive"]
    watches    = [(p, r) for p, r in scored if r.get("recommendation") == "watch"]
    passes     = [(p, r) for p, r in scored if r.get("recommendation") == "pass"]

    sep = "─" * 65
    print(f"\n{sep}")
    print(f"  RESULTS  ({len(scored)} scored)")
    print(sep)

    if deep_dives:
        print(f"\n  DEEP DIVE ({len(deep_dives)})")
        for page, r in deep_dives:
            print(f"  [{r['thesis_fit_score']:3d}] @{page['username']}")
            print(f"        {r.get('one_line_summary', '')}")
            print(f"        match={r.get('primary_thesis_match')}  fit={r.get('category_fit')}")

    if watches:
        print(f"\n  WATCH ({len(watches)})")
        for page, r in watches:
            print(f"  [{r['thesis_fit_score']:3d}] @{page['username']}  {r.get('one_line_summary', '')}")

    print(f"\n  PASS: {len(passes)} project(s)")
    print(f"\n{sep}")
    print(f"  Done. {len(deep_dives)} deep dive(s), {len(watches)} watch(es), {len(passes)} pass(es).")
    print(f"  All scores written to Notion (Status → Scored).")
    print(sep)


if __name__ == "__main__":
    main()
