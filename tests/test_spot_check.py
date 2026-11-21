"""The spot check's draw, on made-up records: the routed model's top four, then six more by the seed, ten companies."""
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("owner_spot_check", HERE.joinpath("owner", "spot_check.py"))
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)


class Draw(unittest.TestCase):
    def setUp(self):
        self.ranking = [{"account": f"Made Up {i:02d}"} for i in range(1, 26)]
        self.recs = [{"account": a["account"], "model": m} for a in self.ranking for m in ("routed", "other", "third")]

    def test_the_ten_cover_ten_companies(self):
        items = sc.choose(self.recs, self.ranking, "routed")
        self.assertEqual(len(items), 10)
        self.assertEqual(len({r["account"] for r in items}), 10)
        self.assertEqual([(r["account"], r["model"]) for r in items[:4]],
                         [(f"Made Up {i:02d}", "routed") for i in range(1, 5)])

    def test_the_draw_is_the_same_every_time(self):
        self.assertEqual(sc.choose(self.recs, self.ranking, "routed"), sc.choose(self.recs, self.ranking, "routed"))


if __name__ == "__main__":
    unittest.main()
