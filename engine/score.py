"""Score each account on fit and intent. Every point traces to a reason, and every intent point to one posting.

Fit (config/fit.json) is who the account is: its industry, its count of open roles (never a headcount) and the share of
its roles in the US. Intent (config/signals.json and config/weights.json) is what it's doing now: each counted signal
earns its family's points times a decay that halves every half_life_days, and half for a temporary role. Two signals
count per family (the most points, then the newer date, then the ID), hiring pace counts up to ten postings, and intent
stops at 100. The score is intent_share times intent plus the rest times fit, and the tier follows the score.

site/scoring.js repeats this arithmetic exactly, and tests/vectors/scoring.json holds the cases both must agree on. Two
rules keep them identical: the decay factor is rounded to three decimals and every point to one decimal, half away from
zero, at the same steps in both languages. So the factor the page shows ("40 × 0.912 = 36.5") is the factor used.
"""
import json
import math
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def round_to(x, places):
    """Half away from zero for the non-negative numbers the score uses, the same in Python and JavaScript."""
    k = 10 ** places
    return math.floor(x * k + 0.5) / k


def load():
    cfg = HERE.joinpath("config")
    weights = json.loads(cfg.joinpath("weights.json").read_text(encoding="utf-8"))
    fit = json.loads(cfg.joinpath("fit.json").read_text(encoding="utf-8"))
    fams = json.loads(cfg.joinpath("signals.json").read_text(encoding="utf-8"))["families"]
    return {"weights": weights, "fit": fit, "points": {k: v["points"] for k, v in fams.items()}}


def decay(age_days, half_life):
    return round_to(0.5 ** (max(age_days, 0) / half_life), 3)


def age_of(posted, on, missing_age):
    if not posted:
        return missing_age
    return (date.fromisoformat(on) - date.fromisoformat(posted)).days


def signal_points(s, on, model, points=None, half_life=None):
    w = model["weights"]
    base = (points or model["points"])[s["family"]]
    age = age_of(s.get("posted", ""), on, w["missing_date_age_days"])
    d = decay(age, half_life or w["half_life_days"])
    mult = w["temporary_multiplier"] if s.get("temporary") else 1
    return {"sid": s["sid"], "family": s["family"], "base": base, "age": age, "decay": d, "mult": mult,
            "points": round_to(base * d * mult, 1)}


def intent(signals, on, model, points=None, half_life=None):
    """(intent 0-100, [counted rows]). Signals posted after `on` don't count yet."""
    w = model["weights"]
    by = {}
    for s in signals:
        if s.get("posted") and s["posted"] > on:
            continue
        if not s.get("posted") and on < (date.fromisoformat(s["read_on"]) - timedelta(days=w["missing_date_age_days"])).isoformat():
            continue
        row = signal_points(s, on, model, points, half_life)
        if row["points"] > 0:
            by.setdefault(s["family"], []).append((row, s.get("posted", "")))
    counted = []
    for fam in sorted(by):
        rows = sorted(by[fam], key=lambda rp: (-rp[0]["points"], _neg_date(rp[1]), rp[0]["sid"]))
        limit = w["pace_cap"] if fam == "pace" else w["per_family"]
        counted += [r for r, _ in rows[:limit]]
    total = 0.0
    for r in counted:
        total = round_to(total + r["points"], 1)
    return min(w["intent_cap"], total), counted


def _neg_date(posted):
    """Sorts newer dates first and a missing date last."""
    return -date.fromisoformat(posted).toordinal() if posted else 0


def fit(account, model):
    """(fit 0-100, [rows]). account holds industry, openings and the counts of postings by region."""
    f = model["fit"]
    ind = f["industry"]["points"].get(account["industry"], 0)
    n = account["openings"]
    band = next((b for b in f["open_roles"]["bands"] if b[0] <= n <= b[1]), None)
    roles = band[2] if band else 0
    known = account["us"] + account["nonus"]
    share = account["us"] / known if known else 0
    us_pts = round_to(f["us_footprint"]["max"] * share, 1)
    rows = [{"part": "industry", "points": ind, "industry": account["industry"]},
            {"part": "open_roles", "points": roles, "openings": n, "band": band[3] if band else ""},
            {"part": "us_footprint", "points": us_pts, "us": account["us"], "known": known}]
    return round_to(ind + roles + us_pts, 1), rows


def tier_of(score, model):
    return next(t for t, floor_ in model["weights"]["tiers"] if score >= floor_)


def score(account, signals, model, intent_share=None, points=None, half_life=None, on=None):
    """{fit, intent, score, tier, fit_rows, intent_rows} for one account."""
    on = on or account["read_on"]
    share = model["weights"]["intent_share"] if intent_share is None else intent_share
    fit_total, fit_rows = fit(account, model)
    intent_total, counted = intent(signals, on, model, points, half_life)
    total = round_to(share * intent_total + (1 - share) * fit_total, 1)
    return {"fit": fit_total, "intent": intent_total, "score": total, "tier": tier_of(total, model),
            "fit_rows": fit_rows, "intent_rows": counted}


def history(account, signals, model, days=None, **kw):
    """[(day, intent, score)] for each of the last `days` days up to the read date, from the postings published by
    then and aged to that day, with fit held flat."""
    days = days or model["weights"]["history_days"]
    end = date.fromisoformat(account["read_on"])
    out = []
    for i in range(days - 1, -1, -1):
        d = (end - timedelta(days=i)).isoformat()
        r = score(account, signals, model, on=d, **kw)
        out.append((d, r["intent"], r["score"]))
    return out
