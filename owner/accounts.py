#!/usr/bin/env python3
"""The owner's machine only, about five minutes: the names skim after the fetch (decision D7).

    python3 owner/accounts.py          (from the build folder)

It prints every company whose public board the fetch read, in columns, so the owner can catch any company the
private list should hold and doesn't. Each one to leave out goes on its own line in private/extra_exclusions.txt,
and python3 owner/exclusions.py runs again. The next build drops it, with no new fetch.
"""
import csv
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def names():
    manifest = HERE.joinpath("data", "raw", "manifest.csv")
    if not manifest.exists():
        return []
    with open(manifest, newline="", encoding="utf-8") as f:
        return sorted(r["company"] for r in csv.DictReader(f) if r["status"] == "ok")


def main():
    found = names()
    if not found:
        print("No boards read yet. Run bash owner/fetch.sh first.")
        return 1
    width = max(len(n) for n in found) + 3
    cols = max(1, shutil.get_terminal_size((120, 40)).columns // width)
    rows = (len(found) + cols - 1) // cols
    for r in range(rows):
        print("".join(found[c * rows + r].ljust(width) for c in range(cols) if c * rows + r < len(found)))
    print(f"\n{len(found)} companies. To leave one out, add its name to private/extra_exclusions.txt on its own line, "
          f"then run python3 owner/exclusions.py again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
