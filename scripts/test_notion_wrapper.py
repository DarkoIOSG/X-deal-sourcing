"""
Standalone test for shared/notion.py
Run: python3 scripts/test_notion_wrapper.py

Tests:
  1. query_candidates  — pull Scored + deep_dive rows
  2. get_project       — fetch first result by notion_id
  3. update_row        — write Notion_Last_Touched timestamp, then verify
"""
import sys, json
sys.path.insert(0, ".")
from datetime import datetime
from shared.notion import (
    query_candidates, get_project, update_row,
    PROP_LAST_TOUCHED, PROP_STATUS, PROP_RECOMMENDATION, PROP_SCORE,
)

sep = "─" * 60

# ── 1. query_candidates ───────────────────────────────────────────────────────
print(f"\n{sep}")
print("TEST 1: query_candidates(status='Scored', recommendation='deep_dive')")
print(sep)

candidates = query_candidates(status="Scored", recommendation="deep_dive")
print(f"Found {len(candidates)} deep_dive candidate(s)\n")

if not candidates:
    print("No deep_dive candidates yet — run score_run.py first, or try:")
    print("  query_candidates(status='Scored', recommendation='watch')")
    sys.exit(0)

for p in candidates[:5]:
    print(f"  [{p['score'] or '?':>3}] @{p['username']}  —  {p['one_liner'][:60]}")
    print(f"        notion_id: {p['notion_id']}")
print()

# ── 2. get_project ────────────────────────────────────────────────────────────
target = candidates[0]
print(f"{sep}")
print(f"TEST 2: get_project('{target['notion_id']}')")
print(sep)

project = get_project(target["notion_id"])
print(f"  Name          : {project['name']}")
print(f"  Username      : @{project['username']}")
print(f"  One-liner     : {project['one_liner']}")
print(f"  Sectors       : {', '.join(project['sectors'])}")
print(f"  Stage         : {project['stage']}")
print(f"  Token status  : {project['token_status']}")
print(f"  Score         : {project['score']}")
print(f"  Recommendation: {project['recommendation']}")
print(f"  Status        : {project['status']}")
if project["scoring_json"]:
    top_reasons = project["scoring_json"].get("top_reasons", [])
    if top_reasons:
        print(f"  Top reasons   :")
        for r in top_reasons:
            print(f"    - {r}")
print()

# ── 3. update_row ─────────────────────────────────────────────────────────────
print(f"{sep}")
print(f"TEST 3: update_row — writing Notion_Last_Touched timestamp")
print(sep)

now = datetime.today().strftime("%Y-%m-%d")
update_row(target["notion_id"], {PROP_LAST_TOUCHED: now})

# Verify the write
verify = get_project(target["notion_id"])
touched = verify.get("scoring_json")   # re-fetch via get_project (not mapped yet)

# Re-fetch raw to confirm
import requests
from config import NOTION_TOKEN
headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28"}
raw = requests.get(f"https://api.notion.com/v1/pages/{target['notion_id']}", headers=headers).json()
last_touched_prop = raw["properties"].get("Notion_Last_Touched", {})
last_touched = (last_touched_prop.get("date") or {}).get("start", "not found")

print(f"  Wrote : {now}")
print(f"  Read  : {last_touched}")
print(f"  {'✓ PASS' if last_touched == now else '✗ FAIL — check Notion_Last_Touched property exists'}")

print(f"\n{sep}")
print("All tests done.")
print(sep)
