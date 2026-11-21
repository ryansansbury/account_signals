"""From the boards as read to the snapshot that ships: parse, verify, redact, place, find signals and check every word.

    python3 -m engine.pipeline          (from the build folder, after bash owner/fetch.sh)

Reads config/accounts.csv, data/raw/manifest.csv, data/raw/boards/*.json and the Gazetteer in data/raw/gazetteer/. A
board counts only when it names its company (verified()), and no company on the private exclusion list, by its own name
or its board's, gets past this step. Every title and posting text is redacted before anything is found, and a signal
drops when its excerpt holds a word from the never list, another demo's name or an excluded company (a tool named in
config/tools.txt excepted, decision D6). Writes, with no description text anywhere:
    data/snapshot/boards.csv      every board read and verified, with its link, read time and count
    data/snapshot/postings.jsonl  every posting's places and date, with its redacted title and link only when a
                                  signal rests on it
    data/snapshot/signals.jsonl   every signal with its redacted excerpt
    data/snapshot/stats.json      the counts the page and DATA.md show
    config/cities.csv             the Gazetteer places the postings use, with a city center from
                                  config/city_overrides.csv where the census point falls on water
It prints counts only and stops if the personal-data scan finds anything in what it wrote.
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from app import never  # noqa: E402
from engine import boards, exclusions, gazetteer, locations, privacy, redact, signals, textsafety  # noqa: E402

RAW = HERE.joinpath("data", "raw")
SNAPSHOT = HERE.joinpath("data", "snapshot")
SEED = HERE.joinpath("config", "accounts.csv")
CITIES = HERE.joinpath("config", "cities.csv")
OVERRIDES = HERE.joinpath("config", "city_overrides.csv")
NAME_PLACES = HERE.joinpath("config", "name_places.txt")
PUBLIC_BOARD = {"greenhouse": "https://job-boards.greenhouse.io/{t}", "lever": "https://jobs.lever.co/{t}",
                "ashby": "https://jobs.ashbyhq.com/{t}"}
BOARD_FIELDS = ["company", "industry", "segment", "provider", "token", "board", "read_at", "openings"]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def verified(company, board_name, postings, token=""):
    """True when the board's own name or a job's company name is the company, or the postings name it: in two
    postings, or in one when the board's token is the company's own name. A guessed token can't bring in someone
    else's board."""
    same = exclusions.Exclusions([company])
    names = {board_name} | {p.get("company", "") for p in postings}
    if any(n and same.matches(n) for n in names):
        return True
    forms = {company, exclusions.core(company).title()} if len(exclusions.core(company)) >= 5 else {company}
    pats = [re.compile(r"(?<![\w-])" + re.escape(f) + r"(?![\w-])") for f in forms]
    hits = sum(1 for p in postings[:80] if any(r.search(p["text"][:8000] + " " + p["title"]) for r in pats))
    full = exclusions.full(company)
    own = {exclusions.squeeze(full), exclusions.squeeze(exclusions.core(company))}
    if len(full.split()[0]) >= 4:
        own.add(full.split()[0])
    token_is_name = re.sub(r"[^a-z0-9]", "", token.lower()) in own
    return hits >= 2 or (hits == 1 and token_is_name)


def clean_posting(p, keep, red, counts):
    p["text"] = textsafety.clean(p["text"])
    for field in ("title", "department", "text"):
        p[field], c = red.redact(p.get(field) or "", keep)
        counts.update({k: v for k, v in c.items() if v})
    return p


def snapshot(raw=None, out=None, seed_path=None, cities_path=None, ex=None, index=None, red=None, cfg=None, tools=None,
             name_places_path=None):
    """Build the snapshot. Returns the stats it writes."""
    raw, out = Path(raw or RAW), Path(out or SNAPSHOT)
    ex = exclusions.load() if ex is None else ex
    if not ex.present:
        raise SystemExit("Stopped: private/exclusions.txt is missing. Run python3 owner/exclusions.py first.")
    if index is None:
        path = gazetteer.find(raw.joinpath("gazetteer"))
        if not path:
            raise SystemExit("Stopped: no Gazetteer places file in data/raw/gazetteer/. Run bash owner/bootstrap.sh.")
        index = gazetteer.index(gazetteer.read(path))
    red = red or redact.Redactor(places={k[1] for k in index})
    cfg, tools = cfg or signals.load_config(), tools or signals.load_tools()
    never_words, foreign_words = never.words(), never.foreign()
    seed = {r["company"]: r for r in read_csv(seed_path or SEED)}
    manifest = [m for m in read_csv(raw.joinpath("manifest.csv")) if m["status"] == "ok"]
    removed, left, dropped = Counter(), Counter(), {}
    rows, posts_out, sigs_out, used = [], [], [], {}
    for m in manifest:
        company = m["company"]
        if company not in seed or ex.matches(company, [m["token"]]) or (m.get("board_name") and ex.matches(m["board_name"])):
            left["excluded or no longer seeded"] += 1
            continue
        board = raw.joinpath("boards", f"{m['provider']}_{m['token']}.json")
        if not board.exists():
            left["missing board file"] += 1
            continue
        postings = boards.parse(m["provider"], m["token"], board.read_bytes())
        if any(p.get("company") and ex.matches(p["company"]) for p in postings):
            left["excluded or no longer seeded"] += 1
            continue
        if not postings:
            left["empty board"] += 1
            continue
        if not verified(company, m.get("board_name", ""), postings, m["token"]):
            left["board didn't name the company"] += 1
            continue
        keep = [company, m.get("board_name", "")]
        read_on = boards.pacific_day(m["fetched_at"])
        for p in postings:
            clean_posting(p, keep, red, removed)
            p["places"] = locations.read(p, index)
            for pl in p["places"]:
                if pl["kind"] == "city":
                    used[(pl["state"], pl["city"])] = (pl["lat"], pl["lon"])
        found = signals.extract(company, postings, read_on, cfg, tools, dropped)
        kept_ids = set()
        for s in found:
            if never.hits(s["excerpt"], never_words) or never.hits(s["excerpt"], foreign_words):
                left["signal with a never or foreign word"] += 1
                continue
            if ex.mentions(s["excerpt"]) or ex.mentions(s["title"]):
                left["signal naming an excluded company"] += 1
                continue
            sigs_out.append(s)
            kept_ids.add(s["posting_id"])
        s_row = seed[company]
        rows.append({"company": company, "industry": s_row["industry"], "segment": s_row["segment"],
                     "provider": m["provider"], "token": m["token"],
                     "board": PUBLIC_BOARD[m["provider"]].format(t=m["token"]), "read_at": m["fetched_at"],
                     "openings": len(postings)})
        for p in postings:
            shown = p["id"] in kept_ids  # titles and links ship only for the postings behind signals
            if shown and p["department"] and ex.mentions(p["department"]):
                p["department"] = ""
                left["department naming an excluded company, blanked"] += 1
            posts_out.append({"id": p["id"], "account": company, "title": p["title"] if shown else "",
                              "department": p["department"] if shown else "",
                              "places": [{k: pl.get(k, "") for k in ("kind", "city", "state")} for pl in p["places"]],
                              "posted": p["posted"].isoformat() if p.get("posted") else "", "date_kind": p["date_kind"],
                              "url": p["url"] if shown else "", "temporary": p.get("employment") == "temporary",
                              "evergreen": p["evergreen"], "repeats": p["repeats"]})
    left["suspicious excerpt"] += dropped.get("suspicious", 0)
    out.mkdir(parents=True, exist_ok=True)
    with open(out.joinpath("boards.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=BOARD_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    out.joinpath("postings.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in posts_out),
                                              encoding="utf-8")
    out.joinpath("signals.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in sigs_out),
                                             encoding="utf-8")
    fixes = {(r["state"], r["city"]): (float(r["lat"]), float(r["lon"])) for r in read_csv(OVERRIDES)} \
        if OVERRIDES.exists() else {}
    with open(cities_path or CITIES, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["city", "state", "lat", "lon", "source"])
        for (st, city), (lat, lon) in sorted(used.items()):
            lat, lon = fixes.get((st, city), (lat, lon))
            src = "city center" if (st, city) in fixes else "census internal point"
            w.writerow([city, st, f"{lat:.6f}", f"{lon:.6f}", src])
    named = sorted({n for p in index.values() for n in p.get("names", [p["name"]]) if len(n.split()) >= 2
                    and set(n.split()) & (red.first | red.last)})
    Path(name_places_path or NAME_PLACES).write_text("# Gazetteer places of two or more words that hold a common first name or surname, so the\n"
                           "# personal-data scan reads San Luis Obispo as a place on any machine. Written by the pipeline.\n"
                           + "\n".join(named) + "\n", encoding="utf-8")
    us = sum(1 for p in posts_out if locations.region_of(p["places"]) == "us")
    placed = sum(1 for p in posts_out if any(pl["kind"] == "city" for pl in p["places"]))
    stats = {"seed": len(seed), "boards_read": len(rows), "postings": len(posts_out), "us_postings": us,
             "postings_in_a_city": placed, "signals": len(sigs_out),
             "signals_by_family": dict(Counter(s["family"] for s in sigs_out)),
             "removed": dict(removed), "left_out": {k: v for k, v in left.items() if v},
             "read_on": max((boards.pacific_day(r["read_at"]) for r in rows), default="")}
    out.joinpath("stats.json").write_text(json.dumps(stats, indent=1) + "\n", encoding="utf-8")
    urls = {p["url"] for p in posts_out} | {r["board"] for r in rows}
    problems = privacy.scan([out.joinpath(n) for n in ("boards.csv", "postings.jsonl", "signals.jsonl")],
                            keep=[r["company"] for r in rows], redactor=red, allowed_urls=urls)
    if problems:
        raise SystemExit("Stopped by the personal-data scan: " + "; ".join(problems))
    return stats


def main():
    st = snapshot()
    print(f"Read {st['boards_read']} boards of {st['seed']} seed companies on {st['read_on']}: {st['postings']} postings "
          f"({st['postings_in_a_city']} placed in a US city), {st['signals']} signals.")
    print("Signals by family: " + ", ".join(f"{k} {v}" for k, v in sorted(st["signals_by_family"].items())) + ".")
    print("Removed from the text: " + (", ".join(f"{k} {v}" for k, v in st["removed"].items()) or "nothing") + ".")
    print("Left out: " + (", ".join(f"{k} {v}" for k, v in st["left_out"].items()) or "nothing") + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
