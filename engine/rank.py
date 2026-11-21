"""From the snapshot to the ranking: each account's hiring hub, fit inputs, score, tier and route at the default weights.

    python3 -m engine.rank          (from the build folder, after python3 -m engine.pipeline)

The hub is the US city with the most open roles, then the most postings behind signals, then the name. It's placed
with Albers USA and the build stops if it lands outside its own state. An account that hires only remotely in the US has
no hub and sits in the remote tray, and one with no US roles stays off the map. Evergreen postings aren't open roles,
so they count nowhere here. Writes data/out/ranking.json (gitignored), which the page's bundle reads.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import boards as boardsmod, geo, locations, route, score  # noqa: E402

SNAPSHOT = HERE.joinpath("data", "snapshot")
CITIES = HERE.joinpath("config", "cities.csv")
OUT = HERE.joinpath("data", "out", "ranking.json")


def read_jsonl(path):
    return [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


def load(snapshot=None, cities=None):
    snap = Path(snapshot or SNAPSHOT)
    with open(snap.joinpath("boards.csv"), newline="", encoding="utf-8") as f:
        boards = list(csv.DictReader(f))
    with open(cities or CITIES, newline="", encoding="utf-8") as f:
        coords = {(r["state"], r["city"]): (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)}
    return boards, read_jsonl(snap.joinpath("postings.jsonl")), read_jsonl(snap.joinpath("signals.jsonl")), coords


def accounts(boards, postings, signals, coords, the_map):
    """One record per account with everything the score, the map and the route need."""
    by_posts, by_sigs = {}, {}
    for p in postings:
        if not p["evergreen"]:
            by_posts.setdefault(p["account"], []).append(p)
    for s in signals:
        by_sigs.setdefault(s["account"], []).append(s)
    out, problems = [], []
    for b in boards:
        name = b["company"]
        posts, sigs = by_posts.get(name, []), by_sigs.get(name, [])
        regions = Counter(locations.region_of(p["places"]) for p in posts)
        cities, remote = Counter(), 0
        signal_posts = Counter()
        sig_postings = {s["posting_id"] for s in sigs}
        for p in posts:
            here = {(pl["state"], pl["city"]) for pl in p["places"] if pl["kind"] == "city"}
            cities.update(here)
            if p["id"] in sig_postings:
                signal_posts.update(here)
            if not here and any(pl["kind"] == "remote" for pl in p["places"]):
                remote += 1
        hub = None
        if cities:
            (st, city), n = sorted(cities.items(), key=lambda kv: (-kv[1], -signal_posts[kv[0]], kv[0][1]))[0]
            lat, lon = coords[(st, city)]
            xy = the_map.place(lat, lon, st)
            if xy is None:
                problems.append(f"{name}'s hub, {city}, {st}, lands outside its state")
            else:
                hub = {"city": city, "state": st, "lat": lat, "lon": lon, "x": round(xy[0], 1), "y": round(xy[1], 1),
                       "roles": n}
        top = [{"city": c, "state": s, "roles": n} for (s, c), n in sorted(cities.items(),
                                                                         key=lambda kv: (-kv[1], kv[0][1]))[:3]]
        out.append({"account": name, "industry": b["industry"], "segment": b["segment"], "provider": b["provider"],
                    "board": b["board"], "read_on": boardsmod.pacific_day(b["read_at"]), "openings": len(posts),
                    "us": regions["us"], "nonus": regions["nonus"], "unknown": regions["unknown"], "hub": hub,
                    "cities": top, "remote_roles": remote, "signal_ids": sorted(s["sid"] for s in sigs)})
    return out, problems


def rank(snapshot=None, cities=None, out=None):
    boards, postings, signals, coords = load(snapshot, cities)
    model, cfg = score.load(), route.load()
    accts, problems = accounts(boards, postings, signals, coords, geo.Map())
    if problems:
        raise SystemExit("Stopped: " + "; ".join(problems))
    by_sigs = {}
    for s in signals:
        by_sigs.setdefault(s["account"], []).append(s)
    for a in accts:
        r = score.score(a, by_sigs.get(a["account"], []), model)
        a.update(fit=r["fit"], intent=r["intent"], score=r["score"], tier=r["tier"], fit_rows=r["fit_rows"],
                 intent_rows=r["intent_rows"])
    read_on = max((a["read_on"] for a in accts), default="")
    routes = route.route([{"account": a["account"], "score": a["score"], "tier": a["tier"],
                           "state": (a["hub"] or {}).get("state", ""), "openings": a["openings"]} for a in accts],
                         cfg, read_on)
    for a in accts:
        a["route"] = routes[a["account"]]
    accts.sort(key=lambda a: (-a["score"], a["account"]))
    path = Path(out or OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"read_on": read_on, "accounts": accts}, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    return accts


def main():
    accts = rank()
    tiers = Counter(a["tier"] for a in accts)
    placed = sum(1 for a in accts if a["hub"])
    print(f"Ranked {len(accts)} accounts: " + ", ".join(f"tier {t} {tiers[t]}" for t in "ABCD") +
          f". {placed} placed on the map, every hub inside its own state.")
    for a in accts[:15]:
        hub = f"{a['hub']['city']}, {a['hub']['state']}" if a["hub"] else "remote"
        print(f"  {a['score']:5.1f} {a['tier']} {a['account']} ({a['industry']}, {hub}): fit {a['fit']}, intent {a['intent']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
