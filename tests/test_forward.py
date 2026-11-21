"""evals/forward.py on made-up companies: how titles compare and sort, what counts as a new role, the window, the
statistics against values worked by hand, and the refusal to run on files that changed after the freeze."""
import csv
import gzip
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import signals as sigmod  # noqa: E402
from evals import forward as fw  # noqa: E402

SPEC = {"base_day": "2026-11-09", "outcome_on_or_after": "2026-12-06", "revops_families": ["revops", "salesops", "crm"],
        "statistics": {"bootstrap_resamples": 200, "seed": 7, "level": 0.95}}


def greenhouse(*jobs):
    return json.dumps({"jobs": [{"id": i, "title": t, "content": "", "location": {"name": "Remote"},
                                 "updated_at": "2026-11-01T00:00:00Z"} for i, t in jobs]}).encode()


class Titles(unittest.TestCase):
    def test_a_title_compares_without_case_punctuation_or_notes(self):
        self.assertEqual(fw.norm("Account Executive, Mid-Market (Remote)"), "account executive mid market")
        self.assertEqual(fw.norm("  "), "")

    def test_titles_sort_by_the_v1_rules(self):
        cfg, fams = sigmod.load_config(), SPEC["revops_families"]
        self.assertEqual(fw.classify("Revenue Operations Manager", cfg, fams), (True, True))
        self.assertEqual(fw.classify("Senior Sales Operations Analyst", cfg, fams)[0], True)
        self.assertEqual(fw.classify("Salesforce Administrator", cfg, fams)[0], True)
        self.assertEqual(fw.classify("Account Executive", cfg, fams), (False, True))
        self.assertEqual(fw.classify("Software Engineer", cfg, fams), (False, False))


class NewRoles(unittest.TestCase):
    def setUp(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(dir=scratch))
        self.base = {
            "Wobbleton Freight": {"provider": "greenhouse", "token": "wobbleton", "ids": ["greenhouse:wobbleton:1"],
                                  "titles": ["account executive"]},
            "Snorvel Energy": {"provider": "greenhouse", "token": "snorvel", "ids": [], "titles": []},
        }

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def read(self, day, rows):
        folder = self.tmp.joinpath(day)
        folder.mkdir()
        with open(folder.joinpath("manifest.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["company", "provider", "token", "status", "openings", "bytes", "fetched_at"])
            w.writeheader()
            for company, token, status, body in rows:
                w.writerow({"company": company, "provider": "greenhouse", "token": token, "status": status,
                            "openings": "", "bytes": "", "fetched_at": ""})
                if body is not None:
                    folder.joinpath(f"greenhouse_{token}.json.gz").write_bytes(gzip.compress(body))

    def test_new_roles_need_a_new_id_and_a_new_title(self):
        self.read("2026-11-15", [("Wobbleton Freight", "wobbleton", "ok", greenhouse(
            ("1", "Account Executive"),                # open on November 9
            ("2", "Account Executive"),                # a repost of a role already open
            ("3", "Revenue Operations Manager"),       # new, revenue operations and go-to-market
            ("4", "General Application"),              # evergreen
            ("5", "Software Engineer")))])             # new, neither
        self.read("2026-11-22", [("Wobbleton Freight", "wobbleton", "ok", greenhouse(
            ("3", "Revenue Operations Manager"), ("6", "Sales Development Representative")))])
        got = fw.outcomes(SPEC, self.base, ["2026-11-15", "2026-11-22"], root=self.tmp)
        self.assertEqual(got["Wobbleton Freight"], {"revops": True, "gtm": 2, "status": "read"})
        self.assertEqual(got["Snorvel Energy"], {"revops": False, "gtm": 0, "status": "gone"})

    def test_the_window_ends_at_the_first_read_on_or_after_the_outcome_day(self):
        days = ["2026-11-09", "2026-11-15", "2026-12-05", "2026-12-06", "2026-12-13"]
        self.assertEqual(fw.window(SPEC, days), (["2026-11-15", "2026-12-05", "2026-12-06"], "2026-12-06"))
        self.assertEqual(fw.window(SPEC, ["2026-11-15"]), (["2026-11-15"], None))


class Statistics(unittest.TestCase):
    def test_auc_by_hand(self):
        self.assertEqual(fw.auc([1, 2, 3, 4], [0, 0, 1, 1]), 1.0)
        self.assertEqual(fw.auc([4, 3, 2, 1], [0, 0, 1, 1]), 0.0)
        self.assertEqual(fw.auc([1, 1, 1, 1], [0, 1, 0, 1]), 0.5)
        self.assertEqual(fw.auc([1, 3, 2, 4], [0, 0, 1, 1]), 0.75)
        self.assertIsNone(fw.auc([1, 2], [1, 1]))

    def test_spearman_and_ranks_by_hand(self):
        self.assertEqual(fw.ranks([10, 20, 20, 30]), [1.0, 2.5, 2.5, 4.0])
        self.assertAlmostEqual(fw.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(fw.spearman([1, 2, 3, 4], [40, 30, 20, 10]), -1.0)

    def test_wilson_by_hand(self):
        self.assertEqual(fw.wilson(0, 10), [0.0, 0.2775])
        self.assertEqual(fw.wilson(5, 10), [0.2366, 0.7634])
        self.assertIsNone(fw.wilson(0, 0))

    def test_a_score_that_sorts_the_outcome_predicts_and_beats_a_flat_baseline(self):
        pred, result = {}, {}
        for i in range(60):
            name = f"Company {i:02d}"
            pred[name] = {"score": i, "tier": "ABCD"[min(3, (59 - i) // 15)], "openings": 10}
            result[name] = {"revops": i >= 40, "gtm": i // 10, "status": "read"}
        got = fw.analyze(SPEC, pred, result)
        p = got["primary"]
        self.assertEqual((p["auc_score"], p["auc_baseline"], p["predicts"], p["beats_baseline"]), (1.0, 0.5, True, True))
        self.assertEqual(p["by_tier"]["A"]["opened"], 15)
        self.assertEqual(got["secondary"]["spearman_score"] > 0.9, True)

    def test_the_resamples_repeat_with_the_seed(self):
        pred = {f"C{i}": {"score": i % 7, "tier": "A", "openings": i} for i in range(30)}
        result = {f"C{i}": {"revops": i % 3 == 0, "gtm": i % 4, "status": "read"} for i in range(30)}
        self.assertEqual(fw.analyze(SPEC, pred, result), fw.analyze(SPEC, pred, result))


class Frozen(unittest.TestCase):
    def test_a_changed_base_stops_the_run(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(dir=scratch))
        try:
            f = tmp.joinpath("base.json")
            f.write_text("{}", encoding="utf-8")
            spec = {"base": {"file": str(f), "sha256": "0" * 64}, "predictions": {"file": str(f), "sha256": fw.sha256(f)}}
            with self.assertRaises(SystemExit):
                fw.checked(spec)
        finally:
            shutil.rmtree(tmp)

    def test_the_spec_holds_the_rules_the_code_reads(self):
        spec = fw.load_spec()
        for key in ("base_day", "outcome_on_or_after", "revops_families", "statistics", "base", "predictions"):
            self.assertIn(key, spec)
        self.assertEqual(spec["statistics"]["bootstrap_resamples"], 2000)


if __name__ == "__main__":
    unittest.main()
