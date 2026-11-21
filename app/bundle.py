"""Everything the page reads, in one file: site/data.js.

The page computes every score, route and history itself with site/scoring.js and site/route.js, which match the Python
on every parity vector, so the bundle carries the inputs (each account's fit facts and its signals) instead of the
results. Signals go as compact rows sorted by their IDs, so a row's place stands in for its ID in the scoring's
tie-break. Titles and link patterns sit in shared tables, a date is its age in days at the read, and a quote ships only
where the page shows it, which keeps the page under a megabyte. The briefs are the recorded runs made with today's
prompt, each with the sources it was written from and the two judges' second read, or in a preview the stand-in's,
labeled. Every visible word the script needs comes from WORDS.md's ui entries.
"""
import csv
import json
from datetime import date
from pathlib import Path

from agents import inputs, judge
from app import mapdraw
from engine import claims, geo, route, score, signals as sigmod

HERE = Path(__file__).resolve().parent.parent
RUNS = HERE.joinpath("data", "ai_runs")
DATE_KINDS = ["published", "created"]
QUIET = ("pace", "stack")  # their rows show a title and a date, so their quotes stay home


def read_jsonl(path):
    return [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


def jread(path, default=None):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def slug(text):
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "x"


def age(posted, read_on):
    if not posted:
        return None
    return (date.fromisoformat(read_on) - date.fromisoformat(posted)).days


def stand_in_records(ranking, sigs, labels, tools):
    """The stand-in's brief for the top 25 with a brief to write: a preview, or a dry build before the scored run.
    It never ships as a result: the export refuses a bundle that holds one."""
    from owner import stand_in
    from owner.record_briefs import dev_names, pick_accounts, record_one
    by = {}
    for s in sigs:
        by.setdefault(s["account"], []).append(s)
    out = []
    for acct in pick_accounts(ranking, "briefs", dev_names()):
        chosen = inputs.pick(acct, by.get(acct["account"], []))
        out.append(record_one(acct, chosen, labels, stand_in.model, "stand-in", "Stand-in (not a model)", "briefs",
                              tools, None, now=acct["read_on"] + "T00:00:00+00:00"))
    return out


def scored_records(runs=None):
    """Today's scored briefs: made with the prompt as it is now, in the briefs split, from a model."""
    out = []
    for p in sorted(Path(runs or RUNS).joinpath("brief").rglob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("model") != "stand-in" and rec.get("split") == "briefs" and rec.get("prompt_hash") == inputs.prompt_hash():
            out.append(rec)
    return out


def judgments(runs=None):
    """{(account, brief model): {judge: record}} for scored briefs, with today's judge prompt."""
    out = {}
    base = Path(runs or RUNS).joinpath("judge")
    if not base.exists():
        return out
    for p in sorted(base.rglob("*.json")):
        if "planted" in p.parts:
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("judge_prompt_hash") != judge.prompt_hash() or not rec["final"]["parts"]:
            continue
        out.setdefault((rec["account"], rec["brief_model"]), {})[rec["judge"]] = rec
    return out


def second_read(rec, judged, judges):
    """The two judges' verdicts on one brief, or None when it hasn't been read with today's brief."""
    got = {}
    for jid in judges:
        j = judged.get(jid)
        if not j or j["brief_prompt_hash"] != rec["prompt_hash"] or j["brief_input_hash"] != rec["input_hash"]:
            return None
        got[jid] = {"label": j["judge_label"], "verdict": j["final"]["verdict"],
                    "parts": {k: [v["verdict"], v["reason"]] for k, v in j["final"]["parts"].items()}}
    return {"both": all(g["verdict"] == "holds up" for g in got.values()), "judges": got}


def flags(check):
    """The sentences a check flagged, with what it found."""
    rows = [{"field": s["field"], "text": s["text"], "problems": s["problems"]}
            for s in (check or {}).get("sentences", []) if s["problems"]]
    return {"rows": rows, "problems": list((check or {}).get("problems", []))}


def problem_count(check):
    return sum(len(s["problems"]) for s in (check or {}).get("sentences", [])) + len((check or {}).get("problems", []))


def shipped_first_names():
    """The first names the live check of an edited first touch reads, less any that the exclusion scan or the never
    list would read as something else. A handful of first names double as company names, and the page names no company
    on the private list in any form."""
    from app import never
    from engine import exclusions
    ex, nv = exclusions.load(), never.words()
    return sorted(n for n in claims.load_first_names() if not ex.mentions(n) and not never.hits(n, nv))


def vector_count():
    """How many parity cases the scoring and routing ports pass, as tests/js/check_scoring.js counts them."""
    n = 0
    for name in ("scoring.json", "routing.json"):
        v = jread(HERE.joinpath("tests", "vectors", name), {})
        n += sum(len(x) for x in v.values() if isinstance(x, list))
    return n


def footprints(root, names):
    """Every US city each account's postings name, with its open roles there, placed the way engine/rank.py places a hub:
    a table of cities ([city, state, x, y]) and for each account [[city's row, roles], ...] from the most roles down. A
    city that lands outside its own state is left out, as it is for a hub."""
    path = root.joinpath("postings.jsonl")
    if not path.exists():
        return [], {}
    coords = {}
    with HERE.joinpath("config", "cities.csv").open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            coords[(r["state"], r["city"])] = (float(r["lat"]), float(r["lon"]))
    want, roles = set(names), {}
    for p in read_jsonl(path):
        if p["account"] not in want or p.get("evergreen"):
            continue
        for pl in p.get("places") or []:
            key = (pl.get("state"), pl.get("city"))
            if pl.get("kind") == "city" and key in coords:
                counts = roles.setdefault(p["account"], {})
                counts[key] = counts.get(key, 0) + 1
    the_map, table, row_of, out = geo.Map(), [], {}, {}
    for name in sorted(roles):
        rows = []
        for (state, city), n in sorted(roles[name].items(), key=lambda kv: (-kv[1], kv[0][1], kv[0][0])):
            if (state, city) not in row_of:
                lat, lon = coords[(state, city)]
                xy = the_map.place(lat, lon, state)
                row_of[(state, city)] = len(table) if xy else None
                if xy:
                    table.append([city, state, round(xy[0], 1), round(xy[1], 1)])
            if row_of[(state, city)] is not None:
                rows.append([row_of[(state, city)], n])
        out[name] = rows
    return table, out


def build(preview=False, words=None, stand_in=False, runs=None):
    """The bundle. stand_in fills the scored briefs with the stand-in's where no model's record exists yet, for a
    dry build on the real snapshot. A preview always uses the stand-in."""
    root = HERE.joinpath("data", "preview") if preview else HERE.joinpath("data", "snapshot")
    ranking = jread(HERE.joinpath("data", "preview" if preview else "out", "ranking.json"))["accounts"]
    sigs = sorted(read_jsonl(root.joinpath("signals.jsonl")), key=lambda s: s["sid"])
    stats = jread(root.joinpath("stats.json"), {})
    cfg = sigmod.load_config()
    families = list(cfg["families"])
    labels = {k: sigmod.as_label(v["label"]) for k, v in cfg["families"].items()}
    tools = claims.load_tools()
    models_cfg = jread(HERE.joinpath("config", "models.json"))
    judges = models_cfg.get("judges", [])
    recs = [] if preview else scored_records(runs)
    if preview or (stand_in and not recs):
        recs = stand_in_records(ranking, sigs, labels, tools)
    read_on = max((a["read_on"] for a in ranking), default="")

    titles, title_ix, tpls, tpl_ix, rows, row_of = [], {}, [], {}, [], {}
    for s in sigs:
        if s["title"] not in title_ix:
            title_ix[s["title"]] = len(titles)
            titles.append(s["title"])
        uid = s["posting_id"].rsplit(":", 1)[-1]
        tpl = s["url"].replace(uid, "{}", 1) if uid and uid in s["url"] else s["url"]
        if tpl not in tpl_ix:
            tpl_ix[tpl] = len(tpls)
            tpls.append(tpl)
        quote = s["excerpt"] if s["excerpt"] != s["title"] and s["family"] not in QUIET else None
        row_of[s["sid"]] = len(rows)
        rows.append([families.index(s["family"]), age(s["posted"], s["read_on"]), DATE_KINDS.index(s["date_kind"]),
                     1 if s.get("temporary") else 0, title_ix[s["title"]], quote, tpl_ix[tpl], uid, s.get("tool") or "",
                     s.get("carried", 1)])

    fp_cities, fp = footprints(root, [a["account"] for a in ranking])
    accounts = []
    for a in ranking:
        hub = a.get("hub")
        accounts.append({"name": a["account"], "industry": a["industry"], "segment": a["segment"],
                         "provider": a.get("provider", ""), "board": a["board"], "openings": a["openings"],
                         "us": a["us"], "nonus": a["nonus"],
                         "hub": [hub["city"], hub["state"], hub["x"], hub["y"], hub["roles"]] if hub else None,
                         "cities": [[c["city"], c["state"], c["roles"]] for c in a["cities"]],
                         "remote": a["remote_roles"], "sigs": sorted(row_of[s] for s in a["signal_ids"] if s in row_of),
                         "fp": fp.get(a["account"], [])})

    judged = judgments(runs) if not preview else {}
    briefs, sources = {}, {}
    for r in sorted(recs, key=lambda r: (r["account"], r["model"])):
        src = {}
        for k, v in r["sources"].items():
            item = {kk: v.get(kk) for kk in ("kind", "title", "excerpt", "text", "posted", "posting_id", "family")
                    if v.get(kk) not in (None, "")}
            if v.get("sid") in row_of:
                item["row"] = row_of[v["sid"]]
            src[k] = item
        if r["account"] in sources and sources[r["account"]] != src:
            raise ValueError(f"{r['account']}: the models' records were written from different sources")
        sources[r["account"]] = src
        final = r["final"]
        briefs.setdefault(r["account"], []).append({
            "model": r["model"], "label": r["label"], "brief": final["brief"], "flags": flags(final["check"]),
            "needs_review": final["needs_review"], "repaired": final["repaired"],
            "first_problems": problem_count(r["attempts"][0]["check"]), "cost": r["cost_usd"], "ms": r["ms"],
            "recorded_at": r["recorded_at"], "stand_in": r["model"] == "stand-in",
            "read": second_read(r, judged.get((r["account"], r["model"]), {}), judges)})

    scores = jread(HERE.joinpath("evals", "scores.json"), {"splits": {}, "route": models_cfg.get("default")})
    if preview or any(b["stand_in"] for bs in briefs.values() for b in bs):
        scores = {"splits": {}, "route": "stand-in", "route_reason": "no model runs in this build"}
    providers = jread(HERE.joinpath("config", "providers.json"), {"providers": {}})["providers"]
    sc = score.load()
    return {
        "meta": {"preview": preview, "stand_in": any(b["stand_in"] for bs in briefs.values() for b in bs),
                 "read_on": read_on,
                 "stats": stats, "terms": {k: {"allowed": v.get("allowed"), "checked": v.get("checked")}
                                           for k, v in providers.items()},
                 "prices_checked": models_cfg.get("prices_checked"), "route": scores.get("route"),
                 "models": {m["id"]: m["label"] for m in models_cfg["models"]}, "judges": judges,
                 "families": families, "date_kinds": DATE_KINDS, "vectors": vector_count()},
        "model": {"weights": jread(HERE.joinpath("config", "weights.json")), "fit": sc["fit"], "points": sc["points"],
                  "labels": labels, "routing": route.load()},
        "map": mapdraw.shapes(), "titles": titles, "links": tpls, "signals": rows, "accounts": accounts, "fpc": fp_cities,
        "sources": sources, "briefs": briefs, "scores": scores,
        "second_read": None if preview else jread(HERE.joinpath("evals", "second_read.json"), None),
        "tools": tools, "first_names": shipped_first_names(), "words": (words.ui() if words else {}),
    }


def write(data, path=None):
    path = Path(path or HERE.joinpath("site", "data.js"))
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    head = json.dumps({"preview": data["meta"]["preview"], "stand_in": data["meta"]["stand_in"]}, separators=(",", ":"))
    path.write_text(f"/* {head} */\nwindow.AS = {text};\n", encoding="utf-8")
    return path.stat().st_size
