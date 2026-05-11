"""Print a project's Notion data by handle. Used to feed context into a manual deep dive."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.notion import query_candidates, get_project

if len(sys.argv) < 2:
    sys.exit("Usage: python3 scripts/get_project.py @handle")

handle = sys.argv[1].lstrip("@").lower()

candidates = query_candidates(status="Scored", recommendation="deep_dive")
project = next((p for p in candidates if p["username"].lower() == handle), None)

if not project:
    # also check watch
    candidates2 = query_candidates(status="Scored", recommendation="watch")
    project = next((p for p in candidates2 if p["username"].lower() == handle), None)

if not project:
    sys.exit(f"@{handle} not found in Notion (Scored + deep_dive or watch)")

print(json.dumps(project, indent=2, ensure_ascii=False))
