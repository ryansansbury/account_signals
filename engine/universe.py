"""The seed list: private/candidates.csv through the private exclusion list and the scans into config/accounts.csv.

    python3 -m engine.universe          (from the build folder, after python3 owner/exclusions.py)

The candidates were written by one rule before any board was read (DATA.md, "The account universe"). The candidate
file stays in private/ because its difference from the seed list would reveal the exclusions, and this prints counts
only. A candidate also leaves when its name holds a word from the never list or another demo's name, or when it repeats
an earlier candidate.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from app import never  # noqa: E402
from engine import exclusions  # noqa: E402

CANDIDATES = HERE.joinpath("private", "candidates.csv")
SEED = HERE.joinpath("config", "accounts.csv")
FIELDS = ["company", "industry", "segment", "provider", "tokens"]
INDUSTRIES = ("software", "logistics", "health care", "manufacturing", "energy", "consumer")
PROVIDERS = ("greenhouse", "lever", "ashby", "")


def build(rows, ex, never_words=None, foreign_words=None):
    """(seed rows, {reason: count}). Raises on a malformed row, since the list was written by hand."""
    never_words = never.words() if never_words is None else never_words
    foreign_words = never.foreign() if foreign_words is None else foreign_words
    left = Counter()
    seen, out = set(), []
    for r in rows:
        if r.get("industry") not in INDUSTRIES or r.get("provider", "") not in PROVIDERS or not r.get("company"):
            raise ValueError(f"row {len(out) + sum(left.values()) + 2} of the candidates is malformed")
        key = exclusions.full(r["company"])
        if key in seen:
            left["repeats"] += 1
            continue
        seen.add(key)
        text = f"{r['company']} {r.get('segment', '')}"
        if never.hits(text, never_words) or never.hits(text, foreign_words):
            left["never or foreign list"] += 1
            continue
        out.append({k: (r.get(k) or "").strip() for k in FIELDS})
    kept, dropped = ex.keep(out)
    left["exclusion list"] += dropped
    return kept, left


def main():
    ex = exclusions.load()
    if not ex.present:
        print("Stopped: private/exclusions.txt is missing. Run python3 owner/exclusions.py first.")
        return 1
    with open(CANDIDATES, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    kept, left = build(rows, ex)
    with open(SEED, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(kept)
    by = Counter(r["industry"] for r in kept)
    print(f"Wrote {len(kept)} of {len(rows)} candidates to config/accounts.csv: "
          + ", ".join(f"{i} {by[i]}" for i in INDUSTRIES) + ".")
    print("Left out: " + (", ".join(f"{n} for the {k}" for k, n in left.items() if n) or "none") + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
