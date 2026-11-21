#!/usr/bin/env python3
"""The owner's machine only, about 20 minutes and about $5: the second read of the scored briefs, by two judges.

    bash owner/run.sh judge                                   after bash owner/run.sh briefs
    python3 owner/judge_briefs.py --stand-in                  a dry run with no model and no network

Each judge in config/models.json's "judges" reads every scored brief against the full text of the postings it rests
on (agents/judge.py) and marks each part holds up, overreaches or wrong. The routed model's dev briefs are judged too,
as written and with an error planted, to show how many planted errors each judge catches. Each judgment goes to
data/ai_runs/judge/<account>/<brief model>.<judge>.json, or under judge/planted/ for the dev briefs, with one repair
request for a malformed reply, and each call adds a line to data/ai_runs/audit.jsonl. A record keeps the verdicts and
their reasons, never the postings' text. A judgment that matches today's judge prompt and input is skipped, so a
stopped run starts again. It runs four calls at a time, needs the prompt and the judge frozen first, and writes
evals/second_read.json with the gate: nine in ten of the routed model's 25 briefs hold up with both judges.
"""
import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from agents import inputs, judge, llm, replay  # noqa: E402
from engine import exclusions, signals as sigmod  # noqa: E402
from evals import freeze  # noqa: E402

RUNS = HERE.joinpath("data", "ai_runs")
RANKING = HERE.joinpath("data", "out", "ranking.json")
SIGNALS = HERE.joinpath("data", "snapshot", "signals.jsonl")
SCORES = HERE.joinpath("evals", "scores.json")
FROZEN = HERE.joinpath("evals", "frozen.json")
OUT = HERE.joinpath("evals", "second_read.json")
CUT_OFF = ("max_tokens", "length")
WORKERS = 4


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "x"


def stand_in(system, user):
    """Every part holds up: the plumbing without a model, never a result."""
    ids = re.findall(r"^(W\d|P|E): ", user.split("The brief's parts:")[-1], re.M)
    parts = [{"id": i, "verdict": "holds up", "reason": "The stand-in passes every part."} for i in ids]
    return json.dumps({"parts": parts}), {"ms": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
                                          "stop_reason": "end_turn"}


def judge_one(model, system, user, ids):
    """(parts or None, attempts) with one repair request after a malformed reply."""
    attempts = []
    for n in range(2):
        reply, meta = model(system, user if n == 0 else judge.repair_message(user, attempts[-1]["reply"],
                                                                           attempts[-1]["errors"]))
        parts, errors = judge.check(reply, ids)
        if errors and meta.get("stop_reason") in CUT_OFF:
            errors = ["the reply was cut off at the output limit before the JSON ended"] + errors
        attempts.append({"reply": reply, "meta": meta, "errors": errors})
        if parts:
            break
    return parts, attempts


def tasks_for(recs, ranking, by_account, labels, judges, clean, ex, raw=None):
    """[(path, header, judge id, user message, part ids)] for every judgment the read needs."""
    out, skipped = [], []
    for r in recs:
        acct = ranking.get(r["account"])
        if acct is None or ex.matches(r["account"]):
            skipped.append(r["account"])
            continue
        brief_message, _ = inputs.message(acct, inputs.pick(acct, by_account.get(r["account"], [])), labels)
        if inputs.input_hash(brief_message) != r["input_hash"]:
            skipped.append(r["account"])
            continue
        posts = judge.postings_for(r, raw)
        if r["split"] == "dev":
            items = [("as written", None, r["final"]["brief"])] + judge.plant(r["final"]["brief"], r["sources"],
                                                                                r["read_on"])
        else:
            items = [(None, None, r["final"]["brief"])]
        for kind, part, brief in items:
            user, ids = judge.message(brief_message, r, brief, posts, clean)
            for jid in judges:
                folder = ("judge", slug(r["account"])) if kind is None else ("judge", "planted", slug(r["account"]))
                name = f"{r['model']}.{jid}.json" if kind is None else f"{slug(kind)}.{r['model']}.{jid}.json"
                header = {"account": r["account"], "split": r["split"], "brief_model": r["model"], "judge": jid,
                          "kind": kind, "part": part, "judge_prompt_hash": judge.prompt_hash(),
                          "brief_prompt_hash": r["prompt_hash"], "brief_input_hash": r["input_hash"],
                          "input_hash": judge.input_hash(user), "read_on": r["read_on"]}
                out.append((Path(*folder).joinpath(name), header, jid, user, ids))
    return out, skipped


def current(path, header):
    """True when a saved judgment matches today's judge prompt and input and could be read, so a rerun skips it."""
    if not path.exists():
        return False
    rec = json.loads(path.read_text(encoding="utf-8"))
    return (rec.get("judge_prompt_hash") == header["judge_prompt_hash"] and rec.get("input_hash") == header["input_hash"]
            and bool(rec["final"]["parts"]))


def load_judged(runs, judges):
    """(scored judgments, planted judgments) from today's records, as agents/judge.summarize takes them."""
    scored, planted = [], []
    for p in sorted(Path(runs).joinpath("judge").rglob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("judge_prompt_hash") != judge.prompt_hash() or rec["judge"] not in judges or not rec["final"]["parts"]:
            continue
        row = {"account": rec["account"], "model": rec["brief_model"], "judge": rec["judge"],
               "verdict": rec["final"]["verdict"], "kind": rec["kind"], "part": rec["part"],
               "parts": rec["final"]["parts"]}
        (planted if rec["split"] == "dev" else scored).append(row)
    return scored, planted


def report(s, labels):
    lines = [f"Second read by {' and '.join(labels[j] for j in s['judges'])}:"]
    if not s["by_model"]:
        lines.append("  No scored brief judged yet. They come after the prompt freeze.")
    for m, x in s["by_model"].items():
        lines.append(f"  {m:14} {x['briefs']} briefs: {x['both_hold']} hold up with both judges, {x['one_holds']} with "
                     f"one, {x['neither_holds']} with neither" + ("" if x["judged_by_both"] == x["briefs"] else
                                                                  f" ({x['briefs'] - x['judged_by_both']} not judged by both yet)"))
    for j, v in s["by_judge"].items():
        lines.append(f"  {labels[j]}: {v['holds up']} hold up, {v['overreaches']} overreach, {v['wrong']} wrong")
    a, p = s["agreement"], s["planted"]
    lines.append(f"The judges agreed on {a['agree']} of {a['briefs']} briefs.")
    lines.append(f"Planted errors caught: {p['by_the_gate']['caught']} of {p['by_the_gate']['of']} by the pair, "
                 + ", ".join(f"{labels[j]} {v['caught']} of {v['of']}" for j, v in p["by_judge"].items()) + ".")
    lines.append("Dev briefs as written that hold up: " + ", ".join(
        f"{labels[j]} {v['holds up']} of {v['of']}" for j, v in p["as_written_holds_up"].items()) + ".")
    g = s["gate"]
    if not g["complete"]:
        state = "isn't complete yet"
    elif not g["trusted"]:
        state = (f"can't count, since the judges caught {g['planted_caught']} of {g['planted_of']} planted errors "
                 f"(it needs {g['planted_need']})")
    else:
        state = "passes" if g["passes"] else "falls short"
    lines.append(f"Gate: {g['held']} of {g['model']}'s {g['of']} briefs hold up with both judges (it needs "
                 f"{g['need']}), so it {state}.")
    return "\n".join(lines)


def main(argv=None, model_for=None, runs=None, raw=None, briefs=None, ex=None):
    """Judgments go to runs (the stand-in's to a scratch folder), and the briefs are read from briefs (or runs). Tests
    hand in made-up exclusions as ex."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stand-in", action="store_true", help="a judge that passes every part, with no model")
    a = ap.parse_args(argv)
    briefs = Path(briefs or runs or RUNS)
    runs = Path(runs or (HERE.joinpath(".cache", "tmp", "judge_stand_in") if a.stand_in else RUNS))
    stages = set(freeze.load(FROZEN).get("stages", {}))
    moved = {stage for stage, _ in freeze.changed(FROZEN)}
    if not a.stand_in and ("judge" not in stages or "judge" in moved):
        print("Stopped: the second read needs the judge frozen as it is now (python3 evals/freeze.py --check shows "
              "what changed).")
        return 1
    # Dev briefs are judged any time. Scored briefs wait until the snapshot and the prompt are frozen as they are now.
    scored_ok = a.stand_in or ({"snapshot", "prompt"} <= stages and not moved & {"snapshot", "prompt"})
    cfg = json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))
    entries = {m["id"]: m for m in cfg["models"]}
    judges = ["stand-in"] if a.stand_in else cfg["judges"]
    labels = {m: e["label"] for m, e in entries.items()}
    labels["stand-in"] = "the stand-in (not a model)"
    route = json.loads(SCORES.read_text(encoding="utf-8"))["route"] if SCORES.exists() else cfg["default"]
    ranking = {x["account"]: x for x in json.loads(RANKING.read_text(encoding="utf-8"))["accounts"]}
    by_account = {}
    for ln in SIGNALS.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            s = json.loads(ln)
            by_account.setdefault(s["account"], []).append(s)
    sig_labels = {k: sigmod.as_label(v["label"]) for k, v in sigmod.load_config()["families"].items()}
    ex = exclusions.load() if ex is None else ex
    if not ex.present:
        print("Stopped: private/exclusions.txt is missing. Run python3 owner/exclusions.py first.")
        return 1
    clean = judge.Cleaner(ex)
    recs = [r for r in replay.load_all(briefs, strict=False) if r["prompt_hash"] == inputs.prompt_hash()
            and r["final"]["brief"] and (r["split"] == "briefs" or r["model"] == route)]
    if not scored_ok and any(r["split"] == "briefs" for r in recs):
        print("The scored briefs wait for the prompt freeze, so this read covers the dev briefs only.")
    recs = [r for r in recs if r["split"] == "dev" or scored_ok]
    todo, skipped = tasks_for(recs, ranking, by_account, sig_labels, judges, clean, ex, raw)
    if skipped:
        print(f"Left out {len(skipped)} brief(s) whose input no longer matches the snapshot.")
    todo = [t for t in todo if not current(runs.joinpath(t[0]), t[1])]
    print(f"{len(todo)} judgments to make, {clean.dropped} posting sentences held back by the cleaning.")
    if a.stand_in:
        backends = {"stand-in": stand_in}
    else:
        if model_for is None:
            from owner import keychain

            def model_for(mid):
                backend = llm.backend_for(entries[mid], keychain.key_for)
                backend.retries = max(backend.retries, 4)  # four calls at a time meet more rate limits
                return backend
        backends = {j: model_for(j) for j in judges}
    system, total, t0, done = judge.prompt_text(), 0.0, time.time(), 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(judge_one, backends[t[2]], system, t[3], t[4]): t for t in todo}
        for fut in as_completed(futures):
            path, header, jid, _, _ = futures[fut]
            done += 1
            name = f"{header['account']}, {header['brief_model']}" + (f", {header['kind']}" if header["kind"] else "")
            try:
                parts, attempts = fut.result()
            except Exception as e:  # a refused call or a dropped connection: report it, keep going, retry on a rerun
                print(f"[{done}/{len(todo)}] {labels[jid]} on {name}: failed ({str(e)[:200]}). Run it again to retry.")
                continue
            if parts:
                parts = {k: dict(v, reason=clean.reason(v["reason"], header["account"])) for k, v in parts.items()}
            rec = dict(header, judge_label=labels[jid],
                       recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       attempts=[{"meta": x["meta"], "errors": x["errors"]} for x in attempts],
                       final={"parts": parts, "verdict": judge.worst(parts) if parts else None,
                              "needs_review": not parts},
                       cost_usd=round(sum(x["meta"].get("cost_usd") or 0 for x in attempts), 6),
                       ms=sum(x["meta"].get("ms") or 0 for x in attempts))
            out = runs.joinpath(path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            with open(runs.joinpath("audit.jsonl"), "a", encoding="utf-8") as f:
                for i, x in enumerate(attempts, 1):
                    f.write(json.dumps({"at": rec["recorded_at"], "kind": "judge", "account": header["account"],
                                        "brief_model": header["brief_model"], "model": jid, "attempt": i,
                                        "ms": x["meta"].get("ms"), "input_tokens": x["meta"].get("input_tokens"),
                                        "output_tokens": x["meta"].get("output_tokens"),
                                        "cost_usd": x["meta"].get("cost_usd"),
                                        "prompt_hash": header["judge_prompt_hash"]}) + "\n")
            total += rec["cost_usd"]
            print(f"[{done}/{len(todo)}] {labels[jid]} on {name}: {rec['final']['verdict'] or 'unreadable reply'}, "
                  f"${rec['cost_usd']:.4f}", flush=True)
    print(f"Judged in {round(time.time() - t0)} s for about ${total:.2f}.")
    scored, planted = load_judged(runs, judges)
    summary = judge.summarize(scored, judges, route, planted)
    if not a.stand_in:
        OUT.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(report(summary, labels))
    return 0


if __name__ == "__main__":
    sys.exit(main())
