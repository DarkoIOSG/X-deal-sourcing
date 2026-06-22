"""
Extract the real project/company name from each voting-queue memo using Claude.

For founder accounts the display name is the person's name, not the project.
Claude reads the memo and returns the actual project name.

Results are cached to data/project_names.json and served by the webapp API.

Run:
  python3 scripts/extract_project_names.py
  python3 scripts/extract_project_names.py --dry-run   # print without saving
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(override=True)

import anthropic
from shared.notion import query_voting_projects

CACHE_PATH = Path(__file__).parent.parent / "webapp" / "project_names.json"
MODEL = "claude-haiku-4-5-20251001"

PROMPT = """\
You are reading a deal-sourcing memo for a startup or crypto project.

Display name on the X (Twitter) account: {display_name}

Memo (first 800 chars):
{memo}

Extract the actual project or company name being built.
- If the account IS the project (e.g. display name "BlockRunAI" = the project), return the display name as-is.
- If the account belongs to a founder or team member, return the project/company name they are building.
- Return ONLY the project name — no explanation, no punctuation, no extra words.
"""


def extract(client: anthropic.Anthropic, display_name: str, memo: str) -> str:
    msg = client.messages.create(
        model=MODEL,
        max_tokens=30,
        messages=[{
            "role": "user",
            "content": PROMPT.format(display_name=display_name, memo=memo[:800]),
        }],
    )
    return msg.content[0].text.strip().strip("\"'")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    client = anthropic.Anthropic()
    projects = query_voting_projects()

    # Load existing cache so we don't re-call for already-resolved entries
    cache: dict[str, str] = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text())

    updated = 0
    skipped = 0
    for p in projects:
        if not p.get("memo"):
            continue

        notion_id = p["notion_id"]
        display_name = p["name"] or p["username"]

        if notion_id in cache and not args.dry_run:
            print(f"@{p['username']:20s}  {display_name!r:35s}  →  {cache[notion_id]!r}  (cached)")
            skipped += 1
            continue

        project_name = extract(client, display_name, p["memo"])
        print(f"@{p['username']:20s}  {display_name!r:35s}  →  {project_name!r}")

        if project_name and project_name.lower() != display_name.lower():
            cache[notion_id] = project_name
            updated += 1

    print(f"\n{updated} new entries extracted, {skipped} already cached.")

    if not args.dry_run:
        CACHE_PATH.parent.mkdir(exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))
        print(f"Saved to {CACHE_PATH}")


if __name__ == "__main__":
    main()
