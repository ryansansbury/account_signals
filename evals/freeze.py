"""Freeze the snapshot and its rules, then the prompt and its checks, so nothing scored is tuned after the fact.

    python3 evals/freeze.py snapshot     after the rule tuning: the snapshot, the seed rules, the weights and the cities
    python3 evals/freeze.py prompt       after the dev round: the prompt, its inputs and the code that checks and scores
    python3 evals/freeze.py judge        before the second read: the judges' prompt, their inputs and the gate
    python3 evals/freeze.py forward      before the first weekly read: the forward test's rules and the code that counts
                                         and tests it
    python3 evals/freeze.py --check      list anything changed since it was frozen, and exit 1 if so

Each stage writes its file hashes into evals/frozen.json once. Freezing a stage again needs --again, and the old hashes
move to "history" with the time, so a change after the fact shows. The recorder refuses the scored run until the prompt
is frozen, and build.py runs the check and labels anything changed since.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

HERE = Path(__file__).resolve().parent.parent
FROZEN = HERE.joinpath("evals", "frozen.json")
STAGES = {
    "snapshot": ["data/snapshot/*", "config/signals.json", "config/weights.json", "config/fit.json",
                 "config/routing.json", "config/cities.csv", "config/city_overrides.csv", "config/tools.txt",
                 "engine/signals.py", "engine/score.py", "engine/route.py", "site/scoring.js", "site/route.js"],
    "prompt": ["prompts/brief.md", "agents/inputs.py", "agents/validate.py", "engine/claims.py", "site/claims.js",
               "evals/score.py"],
    "judge": ["prompts/judge.md", "agents/judge.py"],
    "forward": ["evals/forward_test.json", "evals/forward.py"],
}


def files(stage, root=HERE):
    out = {}
    for pattern in STAGES[stage]:
        for p in sorted(Path(root).glob(pattern)):
            if p.is_file():
                out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return out


def load(path=FROZEN):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {"stages": {}, "history": []}


def changed(path=FROZEN, root=HERE):
    """[(stage, file)] for every frozen file that changed or went missing since its stage froze."""
    data, out = load(path), []
    for stage, info in data["stages"].items():
        now = files(stage, root)
        for f, h in info["files"].items():
            if now.get(f) != h:
                out.append((stage, f))
    return out


def freeze(stage, again=False, path=FROZEN, root=HERE):
    data = load(path)
    if stage in data["stages"] and not again:
        raise SystemExit(f"Stopped: {stage} is frozen already. Freezing it again needs --again, and the old hashes go "
                         f"to history.")
    tz = ZoneInfo("America/Los_Angeles") if ZoneInfo else None
    stamp = datetime.now(tz).isoformat(timespec="seconds")
    if stage in data["stages"]:
        data["history"].append(dict(data["stages"][stage], stage=stage, replaced_at=stamp))
    data["stages"][stage] = {"at": stamp, "files": files(stage, root)}
    Path(path).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return data["stages"][stage]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", nargs="?", choices=sorted(STAGES))
    ap.add_argument("--again", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.check or not a.stage:
        diff = changed()
        for stage, f in diff:
            print(f"changed since the {stage} freeze: {f}")
        print("Nothing changed since it was frozen." if not diff else f"{len(diff)} file(s) changed.")
        return 1 if diff else 0
    got = freeze(a.stage, a.again)
    print(f"Froze {a.stage}: {len(got['files'])} files at {got['at']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
