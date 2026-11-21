"""Score the recorded briefs by model, against the bars set before the first run, and pick the route.

    python3 evals/score.py          (after a run; owner/run.sh calls it)

For each split and model: first drafts that came back as valid JSON and passed every check, briefs repaired once,
briefs that still need review, citation problems and unsupported claims (numbers, dates, recency, quotes, names, tools
and promises) on first drafts and in the final briefs, rule and writing problems, and the cost, seconds and tokens per
brief. A model clears the bars when every brief it shows as checked passes (which the page guarantees by marking the
rest), and no more than two of 25 need review. The route is the cheapest model that clears the bars on dev, the
closest when none does, and Sonnet until dev is in. Writes evals/scores.json, which ships, and prints a table.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from agents import inputs, replay  # noqa: E402

OUT = HERE.joinpath("evals", "scores.json")
UNSUPPORTED = ("number", "date", "recency", "quote", "name", "tool", "promise")
REVIEW_BAR = 2 / 25


def kinds(check):
    if not check:
        return Counter()
    out = Counter(p.split(":", 1)[0] for p in check["problems"])
    for row in check["sentences"]:
        out.update(p.split(":", 1)[0] for p in row["problems"])
    return out


def metrics(recs):
    n = len(recs)
    first = [r["attempts"][0] for r in recs]
    first_k, final_k = Counter(), Counter()
    for a in first:
        first_k.update(kinds(a["check"]))
    for r in recs:
        final_k.update(kinds(r["final"]["check"]))
    mean = (lambda xs: round(sum(xs) / len(xs), 6) if xs else 0)
    review = sum(1 for r in recs if r["final"]["needs_review"])
    return {
        "briefs": n, "first_valid_json": sum(1 for a in first if not a["shape_errors"]),
        "first_passed": sum(1 for a in first if a["check"] and a["check"]["ok"]),
        "repaired": sum(1 for r in recs if r["final"]["repaired"]), "needs_review": review,
        "first_citation_problems": first_k["cite"],
        "first_unsupported": sum(first_k[k] for k in UNSUPPORTED),
        "final_unsupported": sum(final_k[k] for k in UNSUPPORTED),
        "final_rule_problems": final_k["rule"], "final_writing_problems": final_k["writing"],
        "unsupported_by_kind": {k: first_k[k] for k in UNSUPPORTED if first_k[k]},
        "cost_per_brief": mean([r["cost_usd"] for r in recs]),
        "seconds_per_brief": round(mean([r["ms"] for r in recs]) / 1000, 1),
        "tokens_in_per_brief": round(mean([sum(a["meta"].get("input_tokens") or 0 for a in r["attempts"]) for r in recs])),
        "tokens_out_per_brief": round(mean([sum(a["meta"].get("output_tokens") or 0 for a in r["attempts"])
                                            for r in recs])),
        "clears_bars": n > 0 and review / n <= REVIEW_BAR,
    }


def score(recs):
    out = {}
    for r in recs:
        out.setdefault(r["split"], {}).setdefault(r["model"], []).append(r)
    table = {split: {m: metrics(rs) for m, rs in sorted(by.items())} for split, by in out.items()}
    dev = table.get("dev", {})
    clearing = sorted((m for m, x in dev.items() if x["clears_bars"]), key=lambda m: dev[m]["cost_per_brief"])
    closest = sorted(dev, key=lambda m: (dev[m]["needs_review"], dev[m]["cost_per_brief"]))
    route = clearing[0] if clearing else (closest[0] if closest else "claude-sonnet")
    return {"splits": table, "route": route, "route_reason": "cheapest model that clears the bars on dev" if clearing
            else ("closest to the bars on dev" if closest else "the default until dev is in")}


def main():
    recs = replay.load_all(strict=False)
    current = [r for r in recs if r["prompt_hash"] == inputs.prompt_hash()]
    if len(current) < len(recs):
        print(f"Left out {len(recs) - len(current)} record(s) made with an earlier prompt.")
    result = score(current)
    OUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    for split, by in result["splits"].items():
        print(f"{split}:")
        for m, x in by.items():
            print(f"  {m:14} {x['briefs']:3} briefs, {x['first_passed']} passed first time, {x['repaired']} repaired, "
                  f"{x['needs_review']} need review, {x['first_unsupported']} unsupported claims in first drafts, "
                  f"${x['cost_per_brief']:.4f} and {x['seconds_per_brief']} s a brief")
    print(f"Route: {result['route']} ({result['route_reason']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
