"""
Audit: find "passed" Deep_Dived projects that may have been dismissed
because they were too early — not because they were a bad fit.

Targets:
  Status        = Deep_Dived
  Account Type  = Project
  Recommendation= pass
  Stage_Early_Growth = (empty)

Two-pass approach:
  1. Keyword scan of the Memo field — instant, zero cost.
  2. Haiku classification for projects that survive or have a thin memo.

Output: printed report + optional CSV.

Usage:
  python3 scripts/audit_early_passed.py
  python3 scripts/audit_early_passed.py --csv results.csv
"""

import sys
import csv
import json
import argparse
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(override=True)

import anthropic
from config import ANTHROPIC_API_KEY, NOTION_TOKEN, NOTION_DATABASE_ID
from shared.notion import (
    _DB_URL, _HEADERS, _parse_page, update_row,
    PROP_STATUS, PROP_RECOMMENDATION, PROP_STAGE_EARLY_GROWTH,
    PROP_MEMO, PROP_AUDIT_FLAG,
)

# ── Haiku client ──────────────────────────────────────────────────────────────
_ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL = "claude-haiku-4-5"

# ── Keyword lists ─────────────────────────────────────────────────────────────
EARLY_KEYWORDS = [
    "too early", "pre-product", "pre product", "no product", "idea stage",
    "not enough information", "not enough data", "insufficient data",
    "limited information", "limited data", "stealth", "no traction",
    "very early", "extremely early", "seed stage", "pre-launch", "pre launch",
    "just started", "no public info", "no public information",
    "not launched", "building", "coming soon", "whitepaper only",
    "no website", "nothing to evaluate", "hard to assess", "difficult to assess",
    "cannot assess", "can't assess", "unable to assess",
]

CLASSIFICATION_PROMPT = """\
You are a venture capital analyst reviewing why a crypto/web3 project was passed on.

PROJECT DETAILS:
- Name: {name}
- Handle: @{username}
- One-liner: {one_liner}
- Sectors: {sectors}
- Pass memo:
{memo}

TASK:
Classify the PRIMARY reason this project was passed. Choose exactly one:

1. "too_early"   — Passed mainly because there wasn't enough public information yet,
                   the project hadn't launched, was in stealth, or was too pre-product
                   to evaluate properly. The fit with the thesis was unclear due to
                   data scarcity, NOT because the thesis fit was proven weak.

2. "weak_fit"    — Passed because the project clearly doesn't match the fund's thesis,
                   had hard disqualifiers, poor fundamentals, bad team signals, or
                   strong red flags that are independent of how early it is.

3. "unclear"     — The memo doesn't give enough signal to distinguish between the two.

Output ONLY valid JSON, no preamble or markdown:
{{
  "verdict": "too_early" | "weak_fit" | "unclear",
  "confidence": "high" | "medium" | "low",
  "reasoning": "<one sentence explaining the verdict>"
}}
"""


def _query_passed_deep_dived() -> list[dict]:
    """Fetch Deep_Dived + pass pages, then post-filter for Project + empty Stage_Early_Growth."""
    payload = {
        "filter": {
            "and": [
                {"property": PROP_STATUS,         "select": {"equals": "Deep_Dived"}},
                {"property": PROP_RECOMMENDATION, "select": {"equals": "pass"}},
            ]
        },
    }
    pages = []
    cursor = None
    while True:
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(_DB_URL, headers=_HEADERS, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        for raw in data.get("results", []):
            parsed = _parse_page(raw)
            props = raw["properties"]

            # Post-filter: Account Type must be Project (case-insensitive)
            account_type = parsed.get("account_type", "").lower()
            if account_type != "project":
                continue

            # Post-filter: Stage_Early_Growth must be empty
            stage_sel = props.get(PROP_STAGE_EARLY_GROWTH, {}).get("select")
            if stage_sel is not None:
                continue

            # Grab memo (not in _parse_page)
            memo_chunks = props.get(PROP_MEMO, {}).get("rich_text", [])
            parsed["memo"] = " ".join(c["plain_text"] for c in memo_chunks)
            pages.append(parsed)
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return pages


def keyword_scan(memo: str) -> list[str]:
    """Return matched keywords (lowercased memo)."""
    lower = memo.lower()
    return [kw for kw in EARLY_KEYWORDS if kw in lower]


def classify_with_haiku(project: dict) -> dict:
    """Ask Haiku to classify pass reason. Returns {verdict, confidence, reasoning}."""
    prompt = CLASSIFICATION_PROMPT.format(
        name=project.get("name", ""),
        username=project.get("username", ""),
        one_liner=project.get("one_liner") or project.get("memo", "")[:200],
        sectors=", ".join(project.get("sectors", [])) or "unknown",
        memo=project.get("memo", "(no memo)") or "(no memo)",
    )
    resp = _ai.messages.create(
        model=MODEL,
        max_tokens=300,
        system="You are a venture capital analyst. Output only valid JSON.",
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"verdict": "unclear", "confidence": "low", "reasoning": f"parse error: {text[:100]}"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", metavar="FILE", help="Write results to CSV file")
    parser.add_argument("--skip-ai", action="store_true",
                        help="Only run keyword scan, skip Haiku classification")
    args = parser.parse_args()

    print("\n=== Early-Stage Pass Audit ===")
    print("Querying Notion: Deep_Dived + Project + pass + Stage_Early_Growth empty...\n")

    projects = _query_passed_deep_dived()
    print(f"Found {len(projects)} project(s) to audit.\n")

    if not projects:
        print("Nothing to audit — all passed projects already have Stage_Early_Growth filled.")
        return

    results = []

    for p in projects:
        memo = p.get("memo", "") or ""
        matched_kw = keyword_scan(memo)
        memo_len = len(memo.split())

        row = {
            "name":       p.get("name", ""),
            "username":   p.get("username", ""),
            "sectors":    ", ".join(p.get("sectors", [])),
            "memo_words": memo_len,
            "keywords":   ", ".join(matched_kw) if matched_kw else "",
            "verdict":    "",
            "confidence": "",
            "reasoning":  "",
            "notion_id":  p.get("notion_id", ""),
        }

        if args.skip_ai:
            row["verdict"] = "too_early_signal" if matched_kw else "no_signal"
            results.append(row)
            continue

        # Run Haiku classification for all (keywords give context, not the final word)
        try:
            classification = classify_with_haiku(p)
            row["verdict"]    = classification.get("verdict", "unclear")
            row["confidence"] = classification.get("confidence", "")
            row["reasoning"]  = classification.get("reasoning", "")
        except Exception as e:
            row["verdict"]    = "error"
            row["reasoning"]  = str(e)

        # Write Audit_Flag back to Notion (skip on error)
        if row["verdict"] in ("too_early", "weak_fit", "unclear") and p.get("notion_id"):
            try:
                update_row(p["notion_id"], {PROP_AUDIT_FLAG: row["verdict"]})
            except Exception as e:
                print(f"  [warn] could not update Audit_Flag for @{p.get('username', '?')}: {e}")

        results.append(row)
        time.sleep(0.2)  # stay within rate limits

    # ── Print report ──────────────────────────────────────────────────────────
    sep = "─" * 72

    too_early = [r for r in results if r["verdict"] == "too_early"]
    unclear   = [r for r in results if r["verdict"] == "unclear"]
    weak_fit  = [r for r in results if r["verdict"] == "weak_fit"]
    errors    = [r for r in results if r["verdict"] == "error"]

    print(sep)
    print(f"  AUDIT RESULTS  ({len(results)} projects)")
    print(sep)

    if too_early:
        print(f"\n  ⚠  TOO EARLY — worth re-reviewing ({len(too_early)})")
        print("  These were likely passed due to data scarcity, not bad fit.\n")
        for r in sorted(too_early, key=lambda x: x["confidence"], reverse=True):
            print(f"  @{r['username']}  [{r['confidence']} confidence]")
            print(f"    {r['reasoning']}")
            if r["keywords"]:
                print(f"    Keywords: {r['keywords']}")
            print()

    if unclear:
        print(f"\n  ?  UNCLEAR ({len(unclear)})")
        for r in unclear:
            print(f"  @{r['username']}  (memo: {r['memo_words']} words)  {r['reasoning']}")
        print()

    print(f"\n  ✓  WEAK FIT — correctly passed: {len(weak_fit)}")
    if errors:
        print(f"  !  ERRORS: {len(errors)}")

    written = len(too_early) + len(unclear) + len(weak_fit)
    print(f"\n{sep}")
    print(f"  Summary: {len(too_early)} may be too early | {len(unclear)} unclear | {len(weak_fit)} correctly passed")
    if not args.skip_ai:
        print(f"  Audit_Flag written back to Notion for {written} project(s).")
    print(sep)

    # ── CSV export ────────────────────────────────────────────────────────────
    if args.csv:
        out = Path(args.csv)
        with out.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"\n  Results written to {out}")


if __name__ == "__main__":
    main()
