"""Print a project's Notion data by handle. Used to feed context into a manual deep dive."""
import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(override=True)

from shared.notion import _DB_URL, _HEADERS, _parse_page

if len(sys.argv) < 2:
    sys.exit("Usage: python3 scripts/get_project.py @handle")

handle = sys.argv[1].lstrip("@").lower()

payload = {
    "filter": {"property": "Username", "rich_text": {"equals": handle}},
    "page_size": 1,
}
r = requests.post(_DB_URL, headers=_HEADERS, json=payload, timeout=30)
r.raise_for_status()
results = r.json().get("results", [])

if not results:
    sys.exit(f"@{handle} not found in Notion.")

project = _parse_page(results[0])
print(json.dumps(project, indent=2, ensure_ascii=False))
