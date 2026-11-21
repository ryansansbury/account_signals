"""Route each account to a territory and a seat, with a first-touch deadline.

A territory is the region of the account's hiring hub (National when it hires only remotely) and its size, mid-market
or enterprise by its count of open roles. Accounts go round robin across their territory's seats in score order, a
seat holds a capped number of tier A accounts, and an account that finds every seat full goes to the overflow queue.
The deadline counts business days from the read date by tier, and tier D is nurture with no deadline. Seats are labels,
never people. site/route.js repeats this and tests/vectors/routing.json holds the cases both must agree on.
"""
import json
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def load(path=None):
    return json.loads(Path(path or HERE.joinpath("config", "routing.json")).read_text(encoding="utf-8"))


def region_of(state, cfg):
    if not state:
        return cfg["remote_region"]
    return next((r for r, states in cfg["regions"].items() if state in states), cfg["remote_region"])


def business_days(start, n):
    """The date n business days after start (ISO strings), skipping Saturdays and Sundays."""
    d = date.fromisoformat(start)
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d.isoformat()


def route(accounts, cfg, read_on):
    """accounts: [{account, score, tier, state, openings}]. Returns {account: {territory, seat, deadline, overflow}}."""
    order = sorted(accounts, key=lambda a: (-a["score"], a["account"]))
    pointer, held, out = {}, {}, {}
    for a in order:
        segment = "enterprise" if a["openings"] >= cfg["enterprise_from"] else "mid-market"
        territory = f"{region_of(a.get('state'), cfg)} {segment}"
        seats = [f"{territory} {i}" for i in range(1, cfg["seats"] + 1)]
        start = pointer.get(territory, 0)
        cap = cfg["caps"].get(a["tier"])
        seat = None
        for k in range(len(seats)):
            i = (start + k) % len(seats)
            if cap is None or held.get((seats[i], a["tier"]), 0) < cap:
                seat = seats[i]
                pointer[territory] = (i + 1) % len(seats)
                held[(seat, a["tier"])] = held.get((seat, a["tier"]), 0) + 1
                break
        days = cfg["deadline_days"].get(a["tier"])
        out[a["account"]] = {"territory": territory, "seat": seat or "", "overflow": seat is None,
                             "deadline": business_days(read_on, days) if days else ""}
    return out
