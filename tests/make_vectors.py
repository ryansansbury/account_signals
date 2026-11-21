"""Write the parity vectors from the Python, for the JavaScript ports to match exactly.

    python3 tests/make_vectors.py

tests/vectors/scoring.json: rounding and decay at the edges, tiers at their floors, 24 made-up accounts scored under
the default weights and moved weights, and the score over time for three. tests/vectors/routing.json: the same
accounts routed. Seeded, so the files only change when the Python does. tests/test_vectors.py fails when a file is
stale.
"""
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import claims, route, score  # noqa: E402

OUT = HERE.joinpath("tests", "vectors")
READ_ON = "2026-11-09"
FAMILIES = ["revops", "salesops", "crm", "analytics", "leadership", "first_hire", "crm_move", "forecasting",
            "territory", "pace", "stack"]
INDUSTRIES = ["software", "logistics", "health care", "manufacturing", "energy", "consumer"]
STATES = ["CO", "TX", "CA", "NY", "IL", "GA", "MA", "WA", "UT", "MN", "AK", ""]


def accounts(rng, n=24):
    out = []
    end = date.fromisoformat(READ_ON)
    for i in range(n):
        acct = {"account": f"Vexmoor Account {i:02d}", "industry": rng.choice(INDUSTRIES + ["unknown"]),
                "openings": rng.choice([1, 9, 10, 49, 50, 199, 200, rng.randint(1, 400)]),
                "us": rng.randint(0, 40), "nonus": rng.choice([0, 0, 1, 5, 20]), "read_on": READ_ON,
                "state": rng.choice(STATES)}
        sigs = []
        for j in range(rng.randint(0, 16)):
            fam = rng.choice(FAMILIES)
            posted = "" if rng.random() < 0.1 else (end - timedelta(days=rng.choice(
                [0, 1, 7, 29, 30, 31, 45, 60, 89, 90, 120, 200, rng.randint(0, 220)]))).isoformat()
            sigs.append({"sid": f"s{i:02d}{j:02d}{rng.randint(0, 99):02d}", "family": fam, "posted": posted,
                         "temporary": rng.random() < 0.15, "read_on": READ_ON})
        if i == 3:  # an exact tie on points and date, settled by the ID
            sigs += [{"sid": "s99b", "family": "revops", "posted": "2026-11-01", "temporary": False, "read_on": READ_ON},
                     {"sid": "s99a", "family": "revops", "posted": "2026-11-01", "temporary": False, "read_on": READ_ON},
                     {"sid": "s99c", "family": "revops", "posted": "2026-11-01", "temporary": False, "read_on": READ_ON}]
        out.append((acct, sigs))
    return out


ACCOUNT = "Wobbleton Freight"
SENTENCES = [
    ("Wobbleton Freight posted three revenue and sales operations roles in the last 30 days [1][2][3].", True),
    ("A posting from 4 days ago says the team is moving \"off spreadsheets to a single CRM this quarter\" [4].", True),
    ("It posted five operations roles this week [1][2].", True),
    ("Their CRO, Jordan Blake, wants a new CRM [1].", True),
    ("Maria leads revenue operations there [1].", True),
    ("They run Gong across the team [5].", True),
    ("They're moving from HubSpot to Salesforce [5].", True),
    ("Wobbleton Freight has 48 open roles, mostly in Denver [0].", True),
    ("About 92% of its roles are in the US [0].", True),
    ("The first role was posted November 5 [1].", True),
    ("The first role was posted November 6 [1].", True),
    ("It has been hiring since October [1][2][3].", True),
    ("It has been hiring since November [1][2].", True),
    ("The team wants this done in 2026 [4].", True),
    ("Nothing here cites a source.", True),
    ("This cites a source that isn't there [9].", True),
    ("They want \"a unified CRM by spring\" [4].", True),
    ("Their [name removed] is leading it [1].", True),
    ("Hiring in the past month for revenue operations [1][2][3].", True),
    ("It posted 2 roles 11 days ago [2][1].", True),
    ("They mention a $2M budget and Quorvex Corp [4].", True),
    ("A $150K budget sits behind the 48 open roles [0].", True),
    ("Two postings went up in the last two weeks [1][2].", True),
    ("Wobbleton Freight had 48 open roles on its public job board on 2026-11-09 [0].", True),
    ("The first role was published 2026-11-05 [1].", True),
    ("The first role was published 2026-11-04 [1].", True),
    ("The team says it is moving \"off spreadsheets to a single CRM this quarter.\" [4]", True),
    ("Wobbleton Freight's board lists a \"Revenue Operations Manager\" role [1].", True),
    ("Is that one of your priorities this year [1]?", True),
    ("One posting went up this week [1].", True),
    ("Four postings went up this week [1].", True),
    ("Sales hiring shows up in more than one posting [2][3].", True),
    ("The newest posting was 4 days old on the read date [1].", True),
    ("That posting went up 20 days before the read date [3].", True),
    ("That posting went up 21 days before the read date [3].", True),
    ("Wobbleton Freight had 48 open roles on its public job board on 2026-11-09 [0]. Most of them were in Denver [0].",
     True),
    ("The CRM-related postings point to a cleanup [1][4].", True),
    ("The Zorblat-based team is hiring [1].", True),
    ("Wobbleton Freight listed 48 open roles on November 9 [0].", True),
    ("The first role was published November 9 [1].", True),
    ("Two postings went up in the 20 days before that read date [1][3].", True),
    ("Two postings went up in the 10 days before the read date [1][3].", True),
    ("The Revenue Operations Manager role went up in November [1].", True),
    ("The Revenue Operations Manager role went up in October [1].", True),
    ("Postings went up in October and in November [1][2].", True),
    ("The posting from July 2026 is still open [1].", True),
]
TOUCHES = [
    {"subject": "Your CRM move", "cites": [4], "body": "Hi {first_name},\n\nI saw your team is moving off spreadsheets "
     "to a single CRM this quarter. We guarantee a 20% lift in pipeline and it's free.\n\n{sender_name}"},
    {"subject": "A question about your revenue operations hiring this quarter and the CRM", "cites": [],
     "body": "Hello there,\n\nI noticed the {company} posting [1].\n\nThanks"},
    {"subject": "Your forecast", "cites": [1, 4], "body": "Hi {first_name},\n\nYour Revenue Operations Manager posting "
     "says the role will build the forecast your sales leaders use every week. Would a short call help?\n\n{sender_name}"},
    {"subject": "Your revenue operations hire", "cites": [1, 5], "body": "Hi {first_name},\n\nYour team posted a Revenue "
     "Operations Manager role in the last week and is moving from HubSpot to Salesforce. Is the move on track?"
     "\n\n{sender_name}"},
]
BRIEFS = [
    {"why_now": [{"text": "Wobbleton Freight posted three revenue and sales operations roles in the last 30 days [1][2][3]."},
                 {"text": "One posting says the team is moving \"off spreadsheets to a single CRM this quarter\" [4]."}],
     "priority": {"text": "Pipeline reporting that holds up through the CRM move [4]."},
     "questions": ["Which CRM are you moving to?", "Who owns the forecast today?", "What does done look like this quarter?"],
     "unknowns": ["Which CRM they chose", "How big the sales team is"],
     "first_touch": TOUCHES[2]},
    {"why_now": [{"text": "They doubled the sales team [1]."}], "priority": {"text": "Unclear."},
     "questions": ["Why?"], "unknowns": [], "first_touch": TOUCHES[1]},
]


def claim_sources():
    board = {"openings": 48, "read_on": READ_ON, "hub": "Denver, CO", "us_pct": 92}
    sigs = [{"sid": "s1", "title": "Revenue Operations Manager", "excerpt": "Revenue Operations Manager",
             "posted": "2026-11-05", "posting_id": "g:w:101", "family": "revops"},
            {"sid": "s2", "title": "Sales Operations Analyst", "excerpt": "Sales Operations Analyst",
             "posted": "2026-10-29", "posting_id": "g:w:102", "family": "salesops"},
            {"sid": "s3", "title": "Sales Operations Analyst", "excerpt": "Sales Operations Analyst",
             "posted": "2026-10-20", "posting_id": "g:w:103", "family": "salesops"},
            {"sid": "s4", "title": "Revenue Operations Manager", "excerpt": "You'll lead our move off spreadsheets to a "
             "single CRM this quarter and build the forecast our sales leaders use every week.", "posted": "2026-11-05",
             "posting_id": "g:w:101", "family": "crm_move"},
            {"sid": "s5", "title": "Business Systems Lead", "excerpt": "Lead our HubSpot to Salesforce migration.",
             "posted": "2026-09-01", "posting_id": "g:w:104", "family": "stack"}]
    return claims.sources_for(ACCOUNT, board, sigs)


def claim_cases():
    src, tools, fn = claim_sources(), claims.load_tools(), claims.load_first_names()
    out = {"account": ACCOUNT, "read_on": READ_ON, "tools": tools, "sources": src, "sentences": [], "touches": [],
           "briefs": []}
    for text, need in SENTENCES:
        cites = [int(c) for c in claims.MARK.findall(text)]
        out["sentences"].append({"text": text, "cites": cites, "need_cite": need, "expected": claims.check_sentence(
            text, cites, src, ACCOUNT, READ_ON, tools, need_cite=need, first_names=fn)})
    for t in TOUCHES:
        out["touches"].append({"touch": t, "expected": claims.check_touch(t, src, ACCOUNT, READ_ON, tools, fn)})
    for b in BRIEFS:
        out["briefs"].append({"brief": b, "expected": claims.check_brief(b, src, ACCOUNT, READ_ON, tools, first_names=fn)})
    return out


def scored(r):
    return {"fit": r["fit"], "intent": r["intent"], "score": r["score"], "tier": r["tier"],
            "fit_points": [x["points"] for x in r["fit_rows"]],
            "counted": [[x["sid"], x["points"], x["decay"]] for x in r["intent_rows"]]}


def main():
    rng = random.Random(20261109)
    model = score.load()
    moved = [{}, {"intent_share": 1.0}, {"intent_share": 0.0}, {"intent_share": 0.4, "half_life": 7},
             {"half_life": 90, "points": dict(model["points"], revops=10, crm_move=50, pace=3)}]
    cases, hist = [], []
    for i, (acct, sigs) in enumerate(accounts(rng)):
        for opts in moved:
            kw = dict(opts)
            cases.append({"account": acct, "signals": sigs, "opts": opts, "expected": scored(score.score(acct, sigs,
                                                                                                          model, **kw))})
        if i in (0, 3, 7):
            hist.append({"account": acct, "signals": sigs, "opts": {"half_life": 30},
                         "expected": [list(x) for x in score.history(acct, sigs, model, half_life=30)]})
    rounding = [[x, p, score.round_to(x, p)] for x, p in [(0.05, 1), (0.15, 1), (0.25, 1), (36.45, 1), (36.55, 1),
                                                          (39.95, 1), (59.95, 1), (74.95, 1), (0.9115, 3), (0.5005, 3),
                                                          (2.675, 2), (1.005, 2), (99.95, 1), (0.0, 1)]]
    decays = [[a, h, score.decay(a, h)] for h in (7, 30, 90) for a in (0, 1, 29, 30, 31, 60, 365, -3)]
    tiers = [[s, score.tier_of(s, model)] for s in (0.0, 39.9, 40.0, 59.9, 60.0, 74.9, 75.0, 100.0)]
    OUT.mkdir(parents=True, exist_ok=True)
    OUT.joinpath("scoring.json").write_text(json.dumps({"model": model, "round": rounding, "decay": decays,
                                                        "tiers": tiers, "cases": cases, "history": hist},
                                                       separators=(",", ":")) + "\n", encoding="utf-8")
    cfg = route.load()
    sets = []
    for k in range(3):
        accts = []
        for acct, sigs in accounts(random.Random(100 + k), 30):
            r = score.score(acct, sigs, model)
            accts.append({"account": acct["account"], "score": r["score"], "tier": r["tier"], "state": acct["state"],
                          "openings": acct["openings"]})
        if k == 2:  # enough tier A in one territory to overflow both seats
            accts += [{"account": f"Overflow Account {i}", "score": 90 - i, "tier": "A", "state": "CO", "openings": 12}
                      for i in range(8)]
        sets.append({"accounts": accts, "expected": route.route(accts, cfg, READ_ON)})
    days = [[d, n, route.business_days(d, n)] for d, n in [("2026-11-09", 2), ("2026-11-13", 1), ("2026-11-14", 1),
                                                           ("2026-11-15", 5), ("2026-12-31", 10)]]
    OUT.joinpath("routing.json").write_text(json.dumps({"cfg": cfg, "read_on": READ_ON, "sets": sets,
                                                        "business_days": days}, separators=(",", ":")) + "\n",
                                            encoding="utf-8")
    ccases = claim_cases()
    OUT.joinpath("claims.json").write_text(json.dumps(ccases, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} scoring cases, {len(hist)} histories, {len(sets)} routing sets and "
          f"{len(ccases['sentences']) + len(ccases['touches']) + len(ccases['briefs'])} claim cases to tests/vectors/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
