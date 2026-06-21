"""
Daily pipeline runner — executes all daily scripts in sequence.

Run:
  python3 run_daily.py
"""

import subprocess
import sys
from datetime import datetime

SCRIPTS = [
    ["python3", "search_test.py"],
    ["python3", "scripts/fetch_defillama_raises.py"],
    ["python3", "scripts/search_github.py", "--push"],
    ["python3", "scripts/search_google_news.py", "--push"],
    ["python3", "scripts/search_linkedin.py", "--push"],
    ["python3", "scripts/extract_project_names.py"],
]


def run_script(cmd):
    name = " ".join(cmd)
    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"{'='*60}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n[FAILED] {name} exited with code {result.returncode}")
        return False
    return True


def main():
    start = datetime.now()
    print(f"Daily pipeline started at {start.strftime('%Y-%m-%d %H:%M:%S')}")

    failed = []
    for cmd in SCRIPTS:
        if not run_script(cmd):
            failed.append(" ".join(cmd))

    elapsed = (datetime.now() - start).seconds
    print(f"\n{'='*60}")
    print(f"Done in {elapsed}s — {len(SCRIPTS) - len(failed)}/{len(SCRIPTS)} scripts succeeded")
    if failed:
        print("Failed:")
        for f in failed:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
