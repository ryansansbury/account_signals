"""The snapshot stage end to end on the synthetic boards: verified boards only, no excluded company, no description text
and no person's details in what it writes, and the counts it reports."""
import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from engine import exclusions, pipeline, rank

HERE = Path(__file__).resolve().parent.parent
FIXTURES = HERE.joinpath("tests", "fixtures", "boards")
PLACES = [("CO", "Denver", 39.7621, -104.8759), ("CO", "Aurora", 39.7083, -104.7237), ("UT", "Salt Lake City", 40.7777,
          -111.9306), ("MA", "Boston", 42.3389, -71.0181), ("NY", "New York", 40.6635, -73.9387), ("TX", "Austin",
          30.3005, -97.7522)]
INDEX = {(s, n.lower()): {"name": n, "state": s, "lat": la, "lon": lo} for s, n, la, lo in PLACES}


class Snapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        cls.tmp = Path(tempfile.mkdtemp(dir=scratch))
        raw = cls.tmp.joinpath("raw")
        raw.joinpath("boards").mkdir(parents=True)
        for f in FIXTURES.glob("*.json"):
            shutil.copy(f, raw.joinpath("boards", f.name))
        shutil.copy(FIXTURES.joinpath("lever_grindlewick.json"), raw.joinpath("boards", "lever_fizzgig.json"))
        planted = json.loads(FIXTURES.joinpath("greenhouse_wobbleton.json").read_text(encoding="utf-8"))
        for j in planted["jobs"]:
            j["company_name"] = "Quorvex"
        raw.joinpath("boards", "greenhouse_blimpton.json").write_text(json.dumps(planted), encoding="utf-8")
        rows = [("Wobbleton Freight", "greenhouse", "wobbleton", "Wobbleton Freight"),
                ("Grindlewick Health", "lever", "grindlewick", ""), ("Snorvel Energy", "ashby", "snorvel", ""),
                ("Fizzgig Freight", "lever", "fizzgig", ""), ("Blimpton Labs", "greenhouse", "blimpton", "Blimpton")]
        with open(raw.joinpath("manifest.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["company", "status", "provider", "token", "openings", "url", "fetched_at", "board_name", "bytes",
                        "tried"])
            for company, provider, token, name in rows:
                w.writerow([company, "ok", provider, token, "3", "u", "2026-11-09T18:00:00+00:00", name, "1", "x"])
            w.writerow(["Wimbleford Energy", "not found", "", "", "", "", "2026-11-09T18:00:00+00:00", "", "", "x"])
        seed = cls.tmp.joinpath("accounts.csv")
        with open(seed, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["company", "industry", "segment", "provider", "tokens"])
            for company, industry in (("Wobbleton Freight", "logistics"), ("Grindlewick Health", "health care"),
                                      ("Snorvel Energy", "energy"), ("Fizzgig Freight", "logistics"),
                                      ("Blimpton Labs", "software"), ("Wimbleford Energy", "energy")):
                w.writerow([company, industry, "x", "", ""])
        cls.out = cls.tmp.joinpath("snapshot")
        cls.stats = pipeline.snapshot(raw=raw, out=cls.out, seed_path=seed, cities_path=cls.tmp.joinpath("cities.csv"),
                                      ex=exclusions.Exclusions(["Quorvex"]), index=INDEX,
                                      name_places_path=cls.tmp.joinpath("name_places.txt"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_only_verified_boards_and_no_excluded_company(self):
        with open(self.out.joinpath("boards.csv"), newline="", encoding="utf-8") as f:
            names = [r["company"] for r in csv.DictReader(f)]
        self.assertEqual(names, ["Wobbleton Freight", "Grindlewick Health", "Snorvel Energy"])
        self.assertEqual(self.stats["left_out"], {"excluded or no longer seeded": 1, "board didn't name the company": 1})
        everything = "".join(p.read_text(encoding="utf-8") for p in self.out.iterdir())
        self.assertNotIn("Quorvex", everything)
        self.assertNotIn("Blimpton", everything)

    def test_no_description_text_and_no_persons_details(self):
        posts = [json.loads(ln) for ln in self.out.joinpath("postings.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertTrue(all("text" not in p for p in posts))
        everything = "".join(p.read_text(encoding="utf-8") for p in self.out.iterdir())
        for raw in ("Quentworth", "Prunkworth", "wobbleton.example", "555-0142", "@grindlewick_jobs", "#LI-"):
            self.assertNotIn(raw, everything)
        self.assertGreaterEqual(self.stats["removed"]["name"], 2)
        self.assertGreaterEqual(self.stats["removed"]["email"], 1)

    def test_the_ranking_places_each_hub_and_scores_and_routes_every_account(self):
        accts = {a["account"]: a for a in rank.rank(snapshot=self.out, cities=self.tmp.joinpath("cities.csv"),
                                                   out=self.tmp.joinpath("ranking.json"))}
        self.assertEqual({k: (a["hub"]["city"], a["hub"]["state"]) for k, a in accts.items()},
                         {"Wobbleton Freight": ("Denver", "CO"), "Grindlewick Health": ("Boston", "MA"),
                          "Snorvel Energy": ("Austin", "TX")})
        w = accts["Wobbleton Freight"]
        self.assertEqual((w["openings"], w["us"], w["nonus"], w["remote_roles"]), (5, 5, 0, 1))
        self.assertEqual(w["route"]["territory"], "Mountain mid-market")
        self.assertTrue(all(a["tier"] in "ABCD" and a["route"]["seat"] for a in accts.values()))
        self.assertTrue(all(0 <= a["hub"]["x"] <= 975 and 0 <= a["hub"]["y"] <= 610 for a in accts.values()))

    def test_counts_and_places(self):
        st = self.stats
        self.assertEqual((st["boards_read"], st["postings"]), (3, 11))
        self.assertEqual(st["read_on"], "2026-11-09")
        self.assertGreater(st["signals"], 15)
        cities = self.tmp.joinpath("cities.csv").read_text(encoding="utf-8")
        for c in ("Denver", "Salt Lake City", "Boston", "New York", "Austin", "Aurora"):
            self.assertIn(c, cities)


if __name__ == "__main__":
    unittest.main()
