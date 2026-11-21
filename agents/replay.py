"""Replay the recorded briefs, checking each one again exactly as the recorder did.

The build never calls a model. It reads data/ai_runs/brief/<account>/<model>.json, refuses a record made with a prompt
that no longer matches prompts/brief.md, validates the final brief's shape again and runs the claim checks again with
today's code. A record whose fresh check differs from the one it was saved with keeps the fresh result and is listed,
so a change to the checker after the runs shows instead of hiding. Stand-in records stay out unless asked for.
"""
import json
from pathlib import Path

from agents import inputs, validate
from engine import claims

HERE = Path(__file__).resolve().parent.parent
RUNS = HERE.joinpath("data", "ai_runs")


class Stale(Exception):
    pass


def load_all(runs=None, strict=True, stand_in=False):
    out = []
    for p in sorted(Path(runs or RUNS).joinpath("brief").rglob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("model") == "stand-in" and not stand_in:
            continue
        if strict and rec.get("prompt_hash") != inputs.prompt_hash():
            raise Stale(f"{rec['account']} {rec['model']} was recorded with an older prompt. Record it again.")
        out.append(rec)
    return out


def recheck(rec, tools=None, lint=None, first_names=None):
    """(fresh check of the final brief or None, whether it differs from the recorded one)."""
    brief = rec["final"]["brief"]
    if not brief:
        return None, False
    shaped, errors = validate.check(json.dumps(brief))
    if errors:
        return None, True
    sources = {int(k): v for k, v in rec["sources"].items()}
    fresh = claims.check_brief(shaped, sources, rec["account"], rec["read_on"], tools, lint, first_names)
    return fresh, fresh != rec["final"]["check"]
