"""The forward test of the v1 score: did the companies it ranked higher on November 9 go on to open revenue operations
roles, more than their open roles alone would predict? The rules sit in evals/forward_test.json, frozen with this file
before the first weekly read, so the result can't be tuned once the outcomes are known.

    python3 evals/forward.py base      the owner's machine, once, before the freeze: the base index and the predictions
                                       from the November 9 read, into data/raw/weekly/ (never ships)
    python3 evals/forward.py status    the weekly reads on hand and how far the window has run
    python3 evals/forward.py run       once the outcome read is in: evals/forward_result.json and a summary

What counts. The accounts are the ones on the page when the test froze, each with the score, tier and open roles the
v1 rules gave it from the November 9 read. A new role is a posting seen in a weekly read inside the window whose id and
title were both absent on November 9 and that isn't an evergreen posting, counted once per title, so a repost of a
role that was already open isn't new. The window runs from the November 9 read through the first weekly read on or
after December 6. Titles are sorted by the v1 signal rules, which froze with the snapshot: a revenue operations role is
one the revops, salesops or crm title family matches, and a go-to-market role is one the hiring pace rule matches.

The outcomes. The primary one is whether an account opened at least one new revenue operations role in the window. The
secondary one is how many new go-to-market titles it opened. A Form D filed in the window is reported for the accounts
matched to an SEC identity, with no test, since few are expected.

The statistics. For the primary outcome, the area under the ROC curve of the score and of the baseline (open roles on
November 9), each with a 95% interval from 2,000 bootstrap resamples of the accounts, and the interval of their
difference. The score predicts when its interval sits above 0.5, and it beats the baseline when the difference's
interval sits above 0. The outcome rate by tier comes with Wilson 95% intervals. For the secondary outcome, Spearman's
correlation of the score and of the baseline with the count, resampled the same way. An account the exclusion list
drops after the freeze leaves the test and is counted. A board that's gone in every read counts as no new roles and is
counted. Standard library only.
"""
import argparse
import csv
import gzip
import hashlib
import json
import math
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import boards as boardmod  # noqa: E402
from engine import exclusions  # noqa: E402
from engine import signals as sigmod  # noqa: E402

SPEC = HERE.joinpath("evals", "forward_test.json")
RESULT = HERE.joinpath("evals", "forward_result.json")
WEEKLY = HERE.joinpath("data", "raw", "weekly")
RAW_BOARDS = HERE.joinpath("data", "raw", "boards")
RANKING = HERE.joinpath("data", "out", "ranking.json")
BOARDS = HERE.joinpath("data", "snapshot", "boards.csv")
FORM_D = HERE.joinpath("data", "raw", "sec", "form_d.json")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_spec(path=None):
    return json.loads(Path(path or SPEC).read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def norm(title):
    """A title as the test compares it: lower case, notes in parentheses dropped, words joined by single spaces."""
    t = re.sub(r"\([^)]*\)", " ", (title or "").lower())
    return " ".join(re.findall(r"[a-z0-9]+", t))


def classify(title, cfg, families):
    """(a revenue operations role, a go-to-market role) by the v1 title rules."""
    revops = False
    for name in families:
        f = cfg["families"][name]
        if f["not"] and f["not"].search(title or ""):
            continue
        if any(p.search(title or "") for p in f["patterns"]):
            revops = True
    gtm = bool(cfg["pace"].search(title or "")) and not cfg["skip"].search(title or "")
    return revops, gtm


def postings(provider, token, raw):
    return [(p["id"], p["title"], p["evergreen"]) for p in boardmod.parse(provider, token, raw)]


# ---------- the base, once ----------

def build_base(ranking_path=None, boards_path=None, raw_boards=None):
    """({account: {provider, token, ids, titles}}, {account: {score, tier, openings}}) from the November 9 read."""
    ranking = json.loads(Path(ranking_path or RANKING).read_text(encoding="utf-8"))["accounts"]
    with open(boards_path or BOARDS, newline="", encoding="utf-8") as f:
        where = {r["company"]: (r["provider"], r["token"]) for r in csv.DictReader(f)}
    base, pred = {}, {}
    for a in sorted(ranking, key=lambda x: x["account"]):
        provider, token = where[a["account"]]
        raw = Path(raw_boards or RAW_BOARDS).joinpath(f"{provider}_{token}.json").read_bytes()
        posts = postings(provider, token, raw)
        base[a["account"]] = {"provider": provider, "token": token, "ids": sorted({p[0] for p in posts}),
                              "titles": sorted({norm(p[1]) for p in posts if norm(p[1])})}
        pred[a["account"]] = {"score": a["score"], "tier": a["tier"], "openings": a["openings"]}
    return base, pred


def write_base(spec_path=None, out=None):
    spec_path = Path(spec_path or SPEC)
    spec = load_spec(spec_path)
    base_file, pred_file = HERE.joinpath(spec["base"]["file"]), HERE.joinpath(spec["predictions"]["file"])
    if spec["base"].get("sha256") or spec["predictions"].get("sha256"):
        raise SystemExit("Stopped: the spec already holds the base's hashes, so the base is written once and stays.")
    base, pred = build_base()
    for path, data in ((base_file, base), (pred_file, pred)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    spec["base"]["sha256"], spec["predictions"]["sha256"] = sha256(base_file), sha256(pred_file)
    spec["accounts"] = len(pred)
    spec_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote the base for {len(base)} accounts ({sum(len(v['ids']) for v in base.values()):,} postings) and their "
          f"predictions, and put both hashes in {spec_path.name}. Freeze it next: python3 evals/freeze.py forward")
    return 0


# ---------- the reads ----------

def reads(root=None):
    root = Path(root or WEEKLY)
    return sorted(p.name for p in root.iterdir() if p.is_dir() and DAY.match(p.name)) if root.exists() else []


def window(spec, days):
    """(the reads inside the window, the outcome read or None)."""
    after = [d for d in days if d > spec["base_day"]]
    outcome = next((d for d in after if d >= spec["outcome_on_or_after"]), None)
    return ([d for d in after if outcome and d <= outcome] if outcome else after), outcome


def manifest(day, root=None):
    path = Path(root or WEEKLY).joinpath(day, "manifest.csv")
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {m["company"]: m for m in csv.DictReader(f)}


def outcomes(spec, base, days, root=None, cfg=None):
    """{account: {revops, gtm, status}} over the window's reads."""
    cfg = cfg or sigmod.load_config()
    families = spec["revops_families"]
    out = {name: {"new": {}, "seen": False} for name in base}
    for day in days:
        m = manifest(day, root)
        for name, b in base.items():
            row = m.get(name)
            if not row or row["status"] not in ("ok", "empty"):
                continue
            out[name]["seen"] = True
            if row["status"] != "ok":
                continue
            path = Path(root or WEEKLY).joinpath(day, f"{b['provider']}_{b['token']}.json.gz")
            if not path.exists():
                continue
            ids, titles = set(b["ids"]), set(b["titles"])
            for pid, title, evergreen in postings(b["provider"], b["token"], gzip.decompress(path.read_bytes())):
                t = norm(title)
                if evergreen or pid in ids or not t or t in titles or t in out[name]["new"]:
                    continue
                out[name]["new"][t] = classify(title, cfg, families)
    return {name: {"revops": any(v[0] for v in o["new"].values()), "gtm": sum(1 for v in o["new"].values() if v[1]),
                   "status": "read" if o["seen"] else "gone"} for name, o in out.items()}


# ---------- the statistics ----------

def ranks(values):
    """Average ranks from 1, ties sharing their mean."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out, i = [0.0] * len(values), 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def auc(scores, labels):
    """The chance a random positive account outranks a random negative one, ties counting half. None without both."""
    n1 = sum(1 for x in labels if x)
    n0 = len(labels) - n1
    if not n1 or not n0:
        return None
    r = ranks(scores)
    return (sum(r[i] for i, x in enumerate(labels) if x) - n1 * (n1 + 1) / 2) / (n1 * n0)


def spearman(x, y):
    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx, sy = math.sqrt(sum((a - mx) ** 2 for a in rx)), math.sqrt(sum((b - my) ** 2 for b in ry))
    return sxy / (sx * sy) if sx and sy else None


def interval(values, level):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    lo, hi = (1 - level) / 2, 1 - (1 - level) / 2
    pick = lambda q: v[min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))]  # noqa: E731
    return [round(pick(lo), 4), round(pick(hi), 4)]


def wilson(k, n, z=1.959964):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    mid, half = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, mid - half), 4), round(min(1.0, mid + half), 4)]


def resampled(fn, n, spec):
    rng = random.Random(spec["statistics"]["seed"])
    out = []
    for _ in range(spec["statistics"]["bootstrap_resamples"]):
        out.append(fn([rng.randrange(n) for _ in range(n)]))
    return out


def analyze(spec, pred, result):
    """The statistics for the accounts both in the predictions and in the result."""
    names = sorted(n for n in pred if n in result)
    score = [pred[n]["score"] for n in names]
    base = [pred[n]["openings"] for n in names]
    y1 = [result[n]["revops"] for n in names]
    y2 = [result[n]["gtm"] for n in names]
    level = spec["statistics"]["level"]

    def pick(xs, idx):
        return [xs[i] for i in idx]

    def diff(idx):
        a, b = auc(pick(score, idx), pick(y1, idx)), auc(pick(base, idx), pick(y1, idx))
        return None if a is None or b is None else a - b

    def rho_diff(idx):
        a, b = spearman(pick(score, idx), pick(y2, idx)), spearman(pick(base, idx), pick(y2, idx))
        return None if a is None or b is None else a - b

    n = len(names)
    a_s, a_b = auc(score, y1), auc(base, y1)
    ci_s = interval(resampled(lambda i: auc(pick(score, i), pick(y1, i)), n, spec), level)
    ci_b = interval(resampled(lambda i: auc(pick(base, i), pick(y1, i)), n, spec), level)
    ci_d = interval(resampled(diff, n, spec), level)
    tiers = {}
    for t in ("A", "B", "C", "D"):
        idx = [i for i, nm in enumerate(names) if pred[nm]["tier"] == t]
        k = sum(1 for i in idx if y1[i])
        tiers[t] = {"accounts": len(idx), "opened": k, "rate": round(k / len(idx), 4) if idx else None,
                    "interval": wilson(k, len(idx))}
    r_s, r_b = spearman(score, y2), spearman(base, y2)
    rnd = lambda x: None if x is None else round(x, 4)  # noqa: E731
    return {
        "accounts": n,
        "primary": {"opened": sum(1 for x in y1 if x), "auc_score": rnd(a_s), "auc_score_interval": ci_s,
                    "auc_baseline": rnd(a_b), "auc_baseline_interval": ci_b,
                    "difference": rnd(None if a_s is None or a_b is None else a_s - a_b), "difference_interval": ci_d,
                    "predicts": bool(ci_s and ci_s[0] > 0.5), "beats_baseline": bool(ci_d and ci_d[0] > 0),
                    "by_tier": tiers},
        "secondary": {"new_titles": sum(y2), "spearman_score": rnd(r_s),
                      "spearman_score_interval": interval(resampled(lambda i: spearman(pick(score, i), pick(y2, i)), n,
                                                                    spec), level),
                      "spearman_baseline": rnd(r_b),
                      "spearman_baseline_interval": interval(resampled(lambda i: spearman(pick(base, i), pick(y2, i)),
                                                                       n, spec), level),
                      "difference": rnd(None if r_s is None or r_b is None else r_s - r_b),
                      "difference_interval": interval(resampled(rho_diff, n, spec), level)},
    }


# ---------- the commands ----------

def checked(spec):
    """The base and the predictions, refused when either changed since the freeze."""
    files = {}
    for key in ("base", "predictions"):
        path = HERE.joinpath(spec[key]["file"])
        if not path.exists():
            raise SystemExit(f"Stopped: {spec[key]['file']} is missing. The test needs the files it froze with.")
        if sha256(path) != spec[key]["sha256"]:
            raise SystemExit(f"Stopped: {spec[key]['file']} changed after the freeze, so the test can't run on it.")
        files[key] = json.loads(path.read_text(encoding="utf-8"))
    return files["base"], files["predictions"]


def form_d(spec, names, days):
    """The descriptive Form D count, when the SEC identities and filings are on hand."""
    if not FORM_D.exists() or not days:
        return None
    filings = json.loads(FORM_D.read_text(encoding="utf-8"))
    matched = [n for n in names if n in filings]
    end = days[-1]
    filed = [n for n in matched if any(spec["base_day"] < d <= end for d in filings[n])]
    return {"matched": len(matched), "filed_in_window": len(filed)}


def status():
    spec = load_spec()
    days = reads()
    inside, outcome = window(spec, days)
    print(f"Weekly reads on hand: {', '.join(days) if days else 'none yet'}.")
    print(f"The window runs from {spec['base_day']} to the first read on or after {spec['outcome_on_or_after']}: "
          f"{len(inside)} read(s) inside it so far, " +
          (f"and the outcome read of {outcome} is in, so python3 evals/forward.py run gives the result."
           if outcome else "and the outcome read isn't in yet."))
    return 0


def run():
    spec = load_spec()
    base, pred = checked(spec)
    inside, outcome = window(spec, reads())
    if not outcome:
        raise SystemExit(f"Stopped: the outcome read (on or after {spec['outcome_on_or_after']}) isn't in yet.")
    ex = exclusions.load()
    kept = {n: b for n, b in base.items() if not ex.matches(n, [b["token"]])}
    result = outcomes(spec, kept, inside)
    stats = analyze(spec, pred, result)
    out = {"spec_sha256": sha256(SPEC), "base_day": spec["base_day"], "outcome_read": outcome, "reads": inside,
           "left_for_the_exclusion_list": len(base) - len(kept),
           "boards_gone": sum(1 for r in result.values() if r["status"] == "gone"), **stats,
           "form_d": form_d(spec, sorted(kept), inside),
           "per_account": [{"account": n, "score": pred[n]["score"], "tier": pred[n]["tier"],
                            "openings": pred[n]["openings"], "new_revops_role": result[n]["revops"],
                            "new_gtm_titles": result[n]["gtm"], "board": result[n]["status"]} for n in sorted(kept)]}
    RESULT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    p = stats["primary"]
    print(f"{stats['accounts']} accounts over {len(inside)} reads through {outcome}. {p['opened']} opened a new revenue "
          f"operations role. The score's AUC is {p['auc_score']} {p['auc_score_interval']} and the baseline's is "
          f"{p['auc_baseline']} {p['auc_baseline_interval']}, a difference of {p['difference']} "
          f"{p['difference_interval']}. The score {'predicts' if p['predicts'] else 'does not predict'} the outcome "
          f"and {'beats' if p['beats_baseline'] else 'does not beat'} the baseline by the frozen reading.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["base", "status", "run"])
    a = ap.parse_args(argv)
    return {"base": write_base, "status": status, "run": run}[a.command]()


if __name__ == "__main__":
    sys.exit(main())
