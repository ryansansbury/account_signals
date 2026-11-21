"""README.md, written by the build from the same results the page shows, so its numbers never drift from the page.

The screens come from owner/browser_check.py and sit in docs/images/ once owner/shots.sh has copied them, and each
appears only when its file exists. Every sentence passes the copy lint the build runs on the README.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
LIVE = "https://www.ryansansbury.com/account-signals/"
SHOTS = (("map", "The map as a fresh load opens it with the top account selected and the code's sentence on why it leads"),
         ("account", "An account's brief with each citation threaded to the posting it rests on, the second read, and "
                     "the first touch with its live check"),
         ("score", "The score's chart and the arithmetic behind every point beside the weights that re-rank the page"),
         ("list", "Every account with its fit, intent, score, tier, and top reason"),
         ("how", "How it works from the sources with their terms to the scoreboard and the code"),
         ("phone", "The phone's three screens with the tab bar on one line"),
         ("map-dark", "The map in dark mode with the same tiers and rings"))


def months(n):
    return ("January February March April May June July August September October November December").split()[n - 1]


def long_date(iso):
    return f"{months(int(iso[5:7]))} {int(iso[8:10])}" if iso else ""


def gallery():
    have = [(n, alt) for n, alt in SHOTS if HERE.joinpath("docs", "images", f"{n}.png").exists()]
    hero = f"\n![{have[0][1]}](docs/images/{have[0][0]}.png)\n" if have and have[0][0] == "map" else ""
    rest = [f"{alt}.\n\n![{alt}](docs/images/{n}.png)\n" for n, alt in have if n != "map" or not hero]
    return hero, ("\n## Screens\n\n" + "\n".join(rest)) if rest else ""


def board(data):
    sp = (data.get("scores") or {}).get("splits", {}).get("briefs", {})
    sr = (data.get("second_read") or {}).get("by_model", {})
    models = [m for m in data["meta"]["models"] if m in sp]
    if not models:
        return ""
    rows = ["| Model | Passed on the first try | Needs review | Holds up with both judges | API price a brief | Seconds a brief |",
            "|---|---|---|---|---|---|"]
    for m in models:
        s, r = sp[m], sr.get(m)
        star = " (routed)" if m == data["meta"].get("route") else ""
        held = f"{r['both_hold']} of {r['briefs']}" if r else "not read yet"
        rows.append(f"| {data['meta']['models'][m]}{star} | {s['first_passed']} of {s['briefs']} | {s['needs_review']} | "
                    f"{held} | ${s['cost_per_brief']:.4f} | {s['seconds_per_brief']:.1f} |")
    return ("\n".join(rows) + "\n\nEvery call ran through the Claude Code command line on a Claude plan. Each price is what "
            "the same calls would bill through the API.\n")


def gate(data):
    sr = data.get("second_read") or {}
    g = sr.get("gate") or {}
    if not g.get("of"):
        return ""
    caught = sr["planted"]["by_the_gate"]
    head = (f"The judges caught {caught['caught']} of the {caught['of']} errors planted in copies of other briefs. "
            "That's the test their read had to pass to count. ")
    if g.get("passes"):
        return head + f"{g['held']} of the routed model's {g['of']} briefs hold up with both judges against a bar of {g['need']}.\n"
    return head + (f"{g['held']} of the routed model's {g['of']} briefs hold up with both judges where the bar is "
                   f"{g['need']}. That's short of the bar. The page shows every brief's verdict with the judges' reasons.\n")


def render(data):
    m, s = data["meta"], data["meta"].get("stats") or {}
    fams = s.get("signals_by_family") or {}
    scoring = sum(v for k, v in fams.items() if k not in ("pace", "stack"))
    hero, screens = gallery()
    read = (f"The last read covered {s.get('boards_read', 0):,} public job boards on {long_date(m['read_on'])} with "
            f"{s.get('postings', 0):,} postings. It found {s.get('signals', 0):,} signals. {scoring:,} of them count "
            "toward a score as roles or projects.") if s else ""
    lines = [
        "# Account Signals",
        "",
        "Account Signals reads real companies' public job boards to rank the accounts a seller should work first. Every "
        "point of every score has a reason and a posting behind it. The page maps where each company hires and routes it "
        "to a territory with a first-touch deadline. Three Claude models write a cited research brief and a first email "
        "for the top accounts. Code checks every claim against the postings before two of the models read each brief "
        "again as judges. The seller in this example sells revenue operations services. It works at the company level "
        "only and nothing is ever sent.",
        "",
        f"See it live at [ryansansbury.com/account-signals]({LIVE}).",
        hero,
        "## What it does",
        "",
        "- **The read.** An owner script reads each company's public job board through the API its applicant tracking "
        "system offers for that purpose. It honors each host's robots.txt and keeps to the conditions in DATA.md.",
        "- **The signals.** Keyword rules find intent in each posting. A revenue operations role, a forecasting project, "
        "a CRM move, and a new territory each count as one. Every signal keeps its quote, its date, and its link.",
        "- **The score.** Fit comes from the industry, the open roles, and the share of roles in the US. Intent comes from "
        "the signals. Each one loses half its points every 30 days. The page runs the same arithmetic as the build and "
        "re-ranks live as the weights move.",
        "- **The map and the routes.** Each account sits at the city where it posts the most roles. The routing rules "
        "give it a territory, a seat, and a date for the first touch.",
        f"- **The briefs.** Claude Opus 5.5, Claude Sonnet 5.5, and Claude Haiku 5.5 write a brief for every one of the "
        f"top {len(data['briefs'])} accounts from its own postings alone. Every sentence cites the postings it rests on.",
        "- **The checks.** A claim checker reads every number, date, name, tool, and quote against the cited postings. It "
        "runs in Python for the build and in JavaScript on the page. An edited email runs through the same checks as you "
        "type.",
        "- **The second read.** Two model judges read each brief against the full text of its postings. They mark each "
        "part as holding up, overreaching, or wrong. A brief holds up only when both agree. The judges are Opus and "
        "Sonnet.",
        "- **The design.** The page fits one window on a desktop with a dark mode beside the light one. A phone gets the "
        "map, the account, and the score as three screens with a tab bar.",
        "",
        "## The last run",
        "",
        read,
        "",
        board(data),
        gate(data),
        "## Run it",
        "",
        "The build and the tests use Python 3.9 or later with the standard library alone. The page's own checks run "
        "under Node. The page is static and opens from the file system.",
        "",
        "```",
        "python3 -m engine.rank",
        "python3 build.py",
        "python3 tests/run.py",
        "python3 owner/preview_site.py",
        "```",
        "",
        "The read and the model runs are owner scripts. owner/README.md gives their order. The recorded runs ship with "
        "the repo. The page rebuilds from them without an account or a network.",
        "",
        "## Where things are",
        "",
        "| Folder | What it holds |",
        "|---|---|",
        "| `engine/` | the board parsers, redaction, the signals, the scoring, the routing, the map's projection, and the claim checker |",
        "| `agents/` | the model layer, the brief's inputs, its validation, the replay, and the judges |",
        "| `evals/` | the scoreboard, the freeze, and the record of each tuning round |",
        "| `prompts/` | the brief's prompt and the judge's prompt |",
        "| `app/` and `site/` | the build's page, its words, its bundle, and the page's scripts |",
        "| `owner/` | the scripts that read the boards, record the briefs, run the judges, and take the screens |",
        "| `data/` | the redacted snapshot, the ranking, and the recorded runs |",
        "| `tests/` | the unit tests, the parity vectors, and the page's click-through |",
        "",
        "## Read more",
        "",
        "- [DATA.md](DATA.md) gives the sources, their terms, and what never leaves the build machine.",
        "- [docs/DECISIONS.md](docs/DECISIONS.md) records every rule or number changed after the data was seen.",
        screens,
        "## License",
        "",
        "The code is released under the PolyForm Noncommercial License 1.0.0. It allows any noncommercial use. The "
        "companies' postings belong to them. The page links each quote to its posting.",
        "",
    ]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(x for x in lines if x is not None)).rstrip("\n") + "\n"


def write(data, path=None):
    path = Path(path or HERE.joinpath("README.md"))
    path.write_text(render(data), encoding="utf-8")
    return path
