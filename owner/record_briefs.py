#!/usr/bin/env python3
"""The owner's machine only. Record the briefs the page replays, from every model in config/models.json.

    bash owner/run.sh dev                                    the six dev accounts, before the prompt freezes
    bash owner/run.sh briefs                                 the top 25 at the default weights, after the freeze
    python3 owner/record_briefs.py --split dev --stand-in    a dry run with no model and no network

For each account and model it sends the frozen prompt and the account's numbered sources, reads the reply as JSON,
checks every claim, and sends one repair request when the reply is malformed or a check fails. A brief that still fails
is kept as it is and shown as needing review, since catching that is the point. Each record goes to
data/ai_runs/brief/<account>/<model>.json with the prompt and input hashes, both attempts, the checks, tokens, cost
and seconds, and each call adds a line to data/ai_runs/audit.jsonl. A record that already matches today's prompt and
input is skipped, so a stopped run can start again. The scored run needs the prompt frozen first, and no company on
the exclusion list is ever sent.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from agents import inputs, llm, validate  # noqa: E402
from engine import claims, exclusions, geo, signals as sigmod  # noqa: E402

RUNS = HERE.joinpath("data", "ai_runs")
RANKING = HERE.joinpath("data", "out", "ranking.json")
SIGNALS = HERE.joinpath("data", "snapshot", "signals.jsonl")
TOP, DEV = 25, 6


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", exclusions.full(name)).strip("-")[:60] or "account"


def lint_function():
    """The writing rules as a function of one sentence, from tools/lint_copy.py when it's here (it never ships)."""
    tool = HERE.joinpath("tools", "lint_copy.py")
    if not tool.exists():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("lint_copy", str(tool))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    city_state = re.compile(r"(?<=[A-Za-z]), (?=(?:" + "|".join(sorted(geo.STATES)) + r")\b)")

    def lint(sentence):
        # Quoted titles and phrases are the employer's words, checked word for word by the claim checker instead.
        sentence = re.sub(r'["“][^"”]*["”]', "the quote", sentence)
        # The comma in "Lehi, UT" is part of the place's name as source [0] writes it, not a pause.
        sentence = city_state.sub(" ", sentence)
        return [i for s in mod.sentences(sentence) or [sentence] for i in mod.check(s, True)
                if "retired" not in i]
    return lint


def dev_names(path=None):
    """The accounts the prompt was tuned on, from evals/tuning_rounds.json. Once tuned on, an account stays dev."""
    p = Path(path or HERE.joinpath("evals", "tuning_rounds.json"))
    return json.loads(p.read_text(encoding="utf-8")).get("dev_accounts", []) if p.exists() else []


def pick_accounts(ranking, split, pinned=()):
    """The accounts a split covers, in rank order. The scored set is the top 25 with a brief to write, leaving out any
    account the prompt was tuned on, and dev is those tuned-on accounts topped up from just below the 25 to six, so
    the dev set and the scored set never share an account."""
    ranked = [a for a in ranking if inputs.eligible(a)]
    rest = [a for a in ranked if a["account"] not in pinned]
    if split == "briefs":
        return rest[:TOP]
    kept = [a for a in ranked if a["account"] in pinned]
    return [a for a in ranked if a in kept or a in rest[TOP:TOP + max(0, DEV - len(kept))]]


def problem_lines(check):
    out = list(check["problems"])
    for row in check["sentences"]:
        for p in row["problems"]:
            out.append(f'{row["field"]} "{row["text"][:90]}": {p}')
    return out


def repair_message(user, reply, problems):
    return (user + "\nYour previous reply:\n" + reply.strip() + "\n\nIt had these problems:\n"
            + "\n".join(f"- {p}" for p in problems)
            + "\n\nFix every problem and return only the corrected JSON object. Where a claim isn't in the sources, "
              "remove it instead of guessing.\n")


CUT_OFF = ("max_tokens", "length")  # the stop reasons for a reply that hit the output cap


def attempt(model, system, user, sources, account, read_on, tools, lint):
    text, meta = model(system, user)
    brief, errors = validate.check(text)
    if errors and meta.get("stop_reason") in CUT_OFF:
        errors = ["the reply was cut off at the output limit before the JSON ended"] + errors
    check = claims.check_brief(brief, sources, account, read_on, tools, lint) if brief else None
    return {"reply": text, "meta": meta, "shape_errors": errors, "brief": brief, "check": check}


def record_one(account, chosen, labels, model, model_id, label, split, tools, lint, now=None):
    user, sources = inputs.message(account, chosen, labels)
    system = inputs.prompt_text()
    first = attempt(model, system, user, sources, account["account"], account["read_on"], tools, lint)
    attempts = [first]
    if first["shape_errors"] or not first["check"]["ok"]:
        problems = first["shape_errors"] or problem_lines(first["check"])
        attempts.append(attempt(model, system, repair_message(user, first["reply"], problems), sources,
                                account["account"], account["read_on"], tools, lint))
    last = attempts[-1]
    final = {"brief": last["brief"], "check": last["check"], "repaired": len(attempts) > 1,
             "needs_review": not (last["brief"] and last["check"]["ok"])}
    return {"account": account["account"], "model": model_id, "label": label, "split": split,
            "prompt_hash": inputs.prompt_hash(), "input_hash": inputs.input_hash(user), "read_on": account["read_on"],
            "recorded_at": now or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sources": {str(k): v for k, v in sources.items()}, "attempts": attempts, "final": final,
            "cost_usd": round(sum((a["meta"].get("cost_usd") or 0) for a in attempts), 6),
            "ms": sum(a["meta"].get("ms") or 0 for a in attempts)}


def current(path, account, chosen, labels):
    """True when a saved record matches today's prompt and input."""
    if not path.exists():
        return False
    rec = json.loads(path.read_text(encoding="utf-8"))
    user, _ = inputs.message(account, chosen, labels)
    return rec.get("prompt_hash") == inputs.prompt_hash() and rec.get("input_hash") == inputs.input_hash(user)


def frozen_prompt():
    """True when the prompt is frozen and nothing in the snapshot or prompt stages changed since."""
    from evals import freeze
    moved = {stage for stage, _ in freeze.changed()}
    return "prompt" in freeze.load().get("stages", {}) and not moved & {"snapshot", "prompt"}


def main(argv=None, model_for=None, runs=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--split", choices=("dev", "briefs"), required=True)
    ap.add_argument("--models", default="compare", help="compare (every model in the list) or one model id")
    ap.add_argument("--stand-in", action="store_true", help="a deterministic brief with no model and no network")
    a = ap.parse_args(argv)
    runs = Path(runs or RUNS)
    cfg = json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))
    entries = {m["id"]: m for m in cfg["models"]}
    ids = cfg["compare"] if a.models == "compare" else [a.models]
    if a.split == "briefs" and not a.stand_in and not frozen_prompt():
        print("Stopped: the scored run needs the prompt frozen as it is now (python3 evals/freeze.py --check shows "
              "what changed).")
        return 1
    ranking = json.loads(RANKING.read_text(encoding="utf-8"))["accounts"]
    sigs = [json.loads(ln) for ln in SIGNALS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    by_account = {}
    for s in sigs:
        by_account.setdefault(s["account"], []).append(s)
    ex = exclusions.load()
    labels = {k: sigmod.as_label(v["label"]) for k, v in sigmod.load_config()["families"].items()}
    tools, lint = claims.load_tools(), lint_function()
    chosen_accounts = [acc for acc in pick_accounts(ranking, a.split, dev_names()) if not ex.matches(acc["account"])]
    if a.stand_in:
        from owner import stand_in
        ids = ["stand-in"]
    elif model_for is None:
        from owner import keychain

        def model_for(mid):
            return llm.backend_for(entries[mid], keychain.key_for)
    total, t0 = 0.0, time.time()
    for mid in ids:
        model = stand_in.model if a.stand_in else model_for(mid)
        label = "Stand-in (not a model)" if a.stand_in else entries[mid]["label"]
        for n, acct in enumerate(chosen_accounts, 1):
            chosen = inputs.pick(acct, by_account.get(acct["account"], []))
            path = runs.joinpath("brief", slug(acct["account"]), f"{mid}.json")
            if current(path, acct, chosen, labels):
                print(f"[{label} {n}/{len(chosen_accounts)}] {acct['account']}: recorded already")
                continue
            rec = record_one(acct, chosen, labels, model, mid, label, a.split, tools, lint)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            with open(runs.joinpath("audit.jsonl"), "a", encoding="utf-8") as f:
                for i, att in enumerate(rec["attempts"], 1):
                    f.write(json.dumps({"at": rec["recorded_at"], "account": rec["account"], "model": mid,
                                        "split": a.split, "attempt": i, "ms": att["meta"].get("ms"),
                                        "input_tokens": att["meta"].get("input_tokens"),
                                        "output_tokens": att["meta"].get("output_tokens"),
                                        "cost_usd": att["meta"].get("cost_usd"),
                                        "prompt_hash": rec["prompt_hash"]}) + "\n")
            total += rec["cost_usd"]
            state = "needs review" if rec["final"]["needs_review"] else ("passed after a repair" if
                                                                         rec["final"]["repaired"] else "passed")
            print(f"[{label} {n}/{len(chosen_accounts)}] {acct['account']}: {state}, ${rec['cost_usd']:.4f}")
    print(f"Done in {round(time.time() - t0)} s for about ${total:.2f}. The {a.split} run is recorded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
