"""A synthetic preview of the snapshot, so the page can be built and tested before any real board is read.

    python3 generate/preview.py          writes data/preview/ (gitignored, never ships)

About 45 made-up companies, every name built from nonsense syllables and checked against the never and foreign lists,
placed at real US cities, with made-up postings and signals shaped like the real ones. build.py --preview builds the
page from it, the page says it's a preview, and the export refuses a preview build. Seeded, so it's the same each time.
"""
import csv
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from app import never  # noqa: E402

OUT = HERE.joinpath("data", "preview")
READ_ON = "2026-11-09"
CITIES = [("Denver", "CO", 39.7392, -104.9903), ("Boulder", "CO", 40.0150, -105.2705), ("Austin", "TX", 30.2672, -97.7431),
          ("Dallas", "TX", 32.7767, -96.7970), ("Houston", "TX", 29.7604, -95.3698), ("Chicago", "IL", 41.8781, -87.6298),
          ("Atlanta", "GA", 33.7490, -84.3880), ("Boston", "MA", 42.3601, -71.0589), ("New York", "NY", 40.7128, -74.0060),
          ("San Francisco", "CA", 37.7749, -122.4194), ("Los Angeles", "CA", 34.0522, -118.2437),
          ("Seattle", "WA", 47.6062, -122.3321), ("Salt Lake City", "UT", 40.7608, -111.8910),
          ("Phoenix", "AZ", 33.4484, -112.0740), ("Minneapolis", "MN", 44.9778, -93.2650), ("Nashville", "TN", 36.1627,
          -86.7816), ("Raleigh", "NC", 35.7796, -78.6382), ("Columbus", "OH", 39.9612, -82.9988),
          ("Pittsburgh", "PA", 40.4406, -79.9959), ("Miami", "FL", 25.7617, -80.1918), ("Portland", "OR", 45.5152,
          -122.6784), ("Kansas City", "MO", 39.0997, -94.5786), ("Anchorage", "AK", 61.2181, -149.9003)]
FIRST = ["Zor", "Quil", "Blim", "Vex", "Trun", "Flim", "Grob", "Snor", "Pell", "Wux", "Drav", "Kost", "Jib", "Morv", "Plon",
         "Yarb", "Thib", "Crag", "Nub", "Fesk"]
LAST = ["wick", "vane", "lox", "dorf", "mint", "berg", "quist", "tley", "zand", "rook", "mere", "ston", "vell", "garth"]
KIND = {"software": "Labs", "logistics": "Freight", "health care": "Health", "manufacturing": "Works", "energy": "Energy",
        "consumer": "Goods"}
TITLES = {"revops": ["Revenue Operations Manager", "RevOps Analyst", "Director of Revenue Operations"],
          "salesops": ["Sales Operations Analyst", "Sales Operations Manager", "Deal Desk Analyst"],
          "crm": ["Salesforce Administrator", "HubSpot Administrator", "CRM Systems Manager"],
          "analytics": ["Analytics Engineer", "Revenue Analyst", "Sales Analyst"],
          "leadership": ["VP of Sales", "Head of Sales", "Chief Revenue Officer"]}
PHRASES = {"crm_move": ["You'll lead our move from spreadsheets to a single CRM this quarter.",
                        "Own the migration from HubSpot to Salesforce as the team grows."],
           "forecasting": ["Build the forecast our sales leaders use every week.",
                           "Improve forecast accuracy across every region."],
           "territory": ["We're expanding into new territories across the Southeast.",
                         "Help plan territories as we open a second sales office."],
           "first_hire": ["You'll be our first revenue operations hire.",
                          "Build the sales operations function from the ground up."]}


def name(rng, used, industry):
    while True:
        n = f"{rng.choice(FIRST)}{rng.choice(LAST)} {KIND[industry]}"
        if n not in used and not never.hits(n, never.words()) and not never.hits(n, never.foreign()):
            used.add(n)
            return n


def main():
    rng = random.Random(1109)
    end = date.fromisoformat(READ_ON)
    boards, posts, sigs, used = [], [], [], set()
    for i in range(46):
        industry = rng.choice(list(KIND))
        company = name(rng, used, industry)
        token = company.split()[0].lower()
        hub = rng.choice(CITIES[:-1]) if i != 7 else CITIES[-1]
        n_posts = rng.choice([4, 8, 12, 20, 35, 60, 120, 240])
        remote_only = i == 11
        boards.append({"company": company, "industry": industry, "segment": "made up for the preview",
                       "provider": rng.choice(["greenhouse", "lever", "ashby"]), "token": token,
                       "board": f"https://job-boards.greenhouse.io/{token}", "read_at": READ_ON + "T18:00:00+00:00",
                       "openings": n_posts})
        families = [rng.choice(list(TITLES) + list(PHRASES)) for _ in range(rng.choice([0, 1, 2, 4, 6, 8, 9]))]
        for j in range(n_posts):
            pid = f"greenhouse:{token}:{j}"
            fresh = j < len(families)
            posted = (end - timedelta(days=rng.randint(0, 40 if fresh else 150))).isoformat()
            city = hub if rng.random() < 0.6 else rng.choice(CITIES[:-1])
            place = [{"kind": "remote", "city": "", "state": ""}] if remote_only or rng.random() < 0.1 else \
                [{"kind": "city", "city": city[0], "state": city[1]}]
            title = rng.choice(["Account Executive", "Software Engineer", "Customer Success Manager", "Product Designer",
                                "Marketing Manager", "Data Engineer", "Support Specialist"])
            fam = families[j] if j < len(families) else None
            if fam in TITLES:
                title = rng.choice(TITLES[fam])
            posts.append({"id": pid, "account": company, "title": title, "department": "", "places": place,
                          "posted": posted, "date_kind": "published", "url": f"https://job-boards.greenhouse.io/{token}/jobs/{j}",
                          "temporary": False, "evergreen": False, "repeats": 1})
            base = {"account": company, "tool": "", "strength": "", "posting_id": pid, "title": title,
                    "url": posts[-1]["url"], "posted": posted, "date_kind": "published", "temporary": False,
                    "carried": 1, "read_on": READ_ON}
            if fam in TITLES:
                sigs.append(dict(base, family=fam, label=fam, matched=title, excerpt=title, sid=f"s{i:02d}{j:03d}a"))
            elif fam in PHRASES:
                sigs.append(dict(base, family=fam, label=fam, matched="", excerpt=rng.choice(PHRASES[fam]),
                                 sid=f"s{i:02d}{j:03d}b"))
            if title in ("Account Executive", "Customer Success Manager", "Marketing Manager") or fam in TITLES:
                sigs.append(dict(base, family="pace", label="pace", matched="", excerpt=title, sid=f"s{i:02d}{j:03d}p"))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT.joinpath("boards.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(boards[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(boards)
    OUT.joinpath("postings.jsonl").write_text("".join(json.dumps(p) + "\n" for p in posts), encoding="utf-8")
    OUT.joinpath("signals.jsonl").write_text("".join(json.dumps(s) + "\n" for s in sigs), encoding="utf-8")
    with open(OUT.joinpath("cities.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["city", "state", "lat", "lon"])
        for c in CITIES:
            w.writerow(c[:2] + (f"{c[2]:.6f}", f"{c[3]:.6f}"))
    OUT.joinpath("stats.json").write_text(json.dumps({"seed": 60, "boards_read": len(boards), "postings": len(posts),
                                                      "us_postings": len(posts), "postings_in_a_city": len(posts),
                                                      "signals": len(sigs), "read_on": READ_ON, "preview": True,
                                                      "removed": {"name": 12, "email": 5, "phone": 2, "link": 9},
                                                      "left_out": {}}, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote a preview of {len(boards)} made-up companies, {len(posts)} postings and {len(sigs)} signals to "
          f"data/preview/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
