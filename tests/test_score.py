"""The scoring and routing rules, checked by hand on made-up accounts, and the parity vectors kept current."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from engine import route, score

HERE = Path(__file__).resolve().parent.parent
MODEL = score.load()


def sig(sid, family, posted, temporary=False):
    return {"sid": sid, "family": family, "posted": posted, "temporary": temporary, "read_on": "2026-11-09"}


ACCT = {"account": "Wobbleton Freight", "industry": "logistics", "openings": 48, "us": 40, "nonus": 0,
        "read_on": "2026-11-09"}


class Score(unittest.TestCase):
    def test_decay_halves_every_half_life(self):
        self.assertEqual(score.decay(0, 30), 1.0)
        self.assertEqual(score.decay(30, 30), 0.5)
        self.assertEqual(score.decay(60, 30), 0.25)
        self.assertEqual(score.decay(4, 30), 0.912)
        self.assertEqual(score.decay(-2, 30), 1.0)

    def test_every_point_has_its_arithmetic(self):
        r = score.score(ACCT, [sig("s1", "revops", "2026-11-05")], MODEL)
        row = r["intent_rows"][0]
        self.assertEqual((row["base"], row["age"], row["decay"], row["mult"], row["points"]), (40, 4, 0.912, 1, 36.5))
        self.assertEqual(r["intent"], 36.5)

    def test_fit_parts(self):
        total, rows = score.fit(ACCT, MODEL)
        self.assertEqual([x["points"] for x in rows], [36, 30, 30.0])
        self.assertEqual(total, 96.0)
        total, rows = score.fit(dict(ACCT, openings=200, us=3, nonus=1), MODEL)
        self.assertEqual([x["points"] for x in rows], [36, 14, 22.5])

    def test_two_per_family_newest_first_and_temporary_at_half(self):
        sigs = [sig("s1", "salesops", "2026-11-01"), sig("s2", "salesops", "2026-11-08"), sig("s3", "salesops", "2026-10-01"),
                sig("s4", "crm", "2026-11-09", temporary=True)]
        r = score.score(ACCT, sigs, MODEL)
        counted = {x["sid"]: x["points"] for x in r["intent_rows"]}
        self.assertEqual(set(counted), {"s1", "s2", "s4"})
        self.assertEqual(counted["s4"], 15.0)

    def test_pace_counts_ten_postings_and_intent_stops_at_100(self):
        sigs = [sig(f"p{i:02d}", "pace", "2026-11-09") for i in range(14)]
        r = score.score(ACCT, sigs, MODEL)
        self.assertEqual(r["intent"], 10.0)
        lots = [sig(f"x{i}", f, "2026-11-09") for i, f in enumerate(["revops", "revops", "crm_move", "crm_move",
                                                                     "first_hire", "salesops"])]
        self.assertEqual(score.score(ACCT, lots, MODEL)["intent"], 100)

    def test_the_score_and_tier_follow_the_weights(self):
        sigs = [sig("s1", "revops", "2026-11-05"), sig("s2", "crm_move", "2026-10-26")]
        base = score.score(ACCT, sigs, MODEL)
        self.assertEqual(base["score"], score.round_to(0.6 * base["intent"] + 0.4 * base["fit"], 1))
        self.assertEqual(score.score(ACCT, sigs, MODEL, intent_share=0.0)["score"], base["fit"])
        self.assertEqual(score.tier_of(75.0, MODEL), "A")
        self.assertEqual(score.tier_of(74.9, MODEL), "B")
        self.assertEqual(score.tier_of(39.9, MODEL), "D")

    def test_history_counts_only_what_had_been_posted(self):
        sigs = [sig("s1", "revops", "2026-11-05")]
        h = score.history(ACCT, sigs, MODEL)
        self.assertEqual(len(h), 90)
        self.assertEqual(h[-1][0], "2026-11-09")
        before = [x for x in h if x[0] < "2026-11-05"]
        self.assertTrue(all(x[1] == 0 for x in before))
        self.assertEqual(dict((d, i) for d, i, _ in h)["2026-11-05"], 40.0)


class Route(unittest.TestCase):
    def test_territories_rotation_caps_and_deadlines(self):
        cfg = route.load()
        accts = [{"account": f"Made Up {i}", "score": 90 - i, "tier": "A", "state": "CO", "openings": 12} for i in range(7)]
        accts.append({"account": "Remote Only", "score": 50, "tier": "C", "state": "", "openings": 80})
        r = route.route(accts, cfg, "2026-11-13")
        seats = [r[f"Made Up {i}"]["seat"] for i in range(7)]
        self.assertEqual(seats[:6], ["Mountain mid-market 1", "Mountain mid-market 2"] * 3)
        self.assertTrue(r["Made Up 6"]["overflow"])
        self.assertEqual(r["Made Up 0"]["deadline"], "2026-11-17")
        self.assertEqual(r["Remote Only"]["territory"], "National enterprise")
        self.assertEqual(r["Remote Only"]["deadline"], "2026-11-27")


class Vectors(unittest.TestCase):
    def test_the_vectors_are_current(self):
        before = {p.name: p.read_bytes() for p in HERE.joinpath("tests", "vectors").glob("*.json")}
        subprocess.run([sys.executable, str(HERE.joinpath("tests", "make_vectors.py"))], check=True,
                       capture_output=True)
        after = {p.name: p.read_bytes() for p in HERE.joinpath("tests", "vectors").glob("*.json")}
        self.assertEqual(before, after, "tests/vectors/ was stale, so it was rewritten. Run the tests again.")
        self.assertTrue(json.loads(after["scoring.json"])["cases"])


if __name__ == "__main__":
    unittest.main()
