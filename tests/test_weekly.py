"""owner/weekly.py offline, through a fake transport and made-up companies: the read kept by its day, the statuses, the
exclusion list before the read and after it, the stale-list gate, and a stopped read that resumes."""
import contextlib
import csv
import gzip
import io
import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

import sys  # noqa: E402

sys.path.insert(0, str(HERE))
from owner import fetch as fx  # noqa: E402
from owner import weekly as wk  # noqa: E402

JOBS = json.dumps({"jobs": [{"id": "1", "title": "Revenue Operations Analyst"}, {"id": "2", "title": "Engineer"}]}).encode()
LEVER = json.dumps([{"id": "a", "text": "Account Executive"}]).encode()


class WeeklyRead(unittest.TestCase):
    def setUp(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(dir=scratch))
        boards = self.tmp.joinpath("boards.csv")
        boards.write_text("company,industry,segment,provider,token,board,read_at,openings\n"
                          "Wobbleton Freight,logistics,x,greenhouse,wobbleton,u,t,2\n"
                          "Grindlewick Health,health care,x,lever,grindlewick,u,t,1\n"
                          "Quorvex Holdings,software,x,greenhouse,quorvex,u,t,9\n"
                          "Snorvel Energy,energy,x,greenhouse,snorvel,u,t,3\n", encoding="utf-8")
        providers = self.tmp.joinpath("providers.json")
        providers.write_text(json.dumps({"max_age_days": 45, "providers": {
            p: {"allowed": True, "checked": date.today().isoformat(), "status": "test"} for p in ("greenhouse", "lever")}}),
            encoding="utf-8")
        self.excluded = self.tmp.joinpath("exclusions.txt")
        self.excluded.write_text("# made up\nQuorvex Holdings\n", encoding="utf-8")
        self.saved = (wk.BOARDS, wk.WEEKLY, wk.today, fx.PROVIDERS, fx.EXCLUDED, fx.DELAY, fx.RETRY_WAITS,
                      fx.HOST_DELAY, fx.get, dict(fx.SENT))
        wk.BOARDS, wk.WEEKLY = boards, self.tmp.joinpath("weekly")
        wk.today = lambda: "2026-11-15"
        fx.PROVIDERS, fx.EXCLUDED = providers, self.excluded
        fx.DELAY, fx.RETRY_WAITS, fx.HOST_DELAY = 0, (0, 0), {}
        fx.SENT["n"] = 0
        fx.ROBOTS.clear()
        fx.LAST.clear()
        self.calls = []
        self.table = {"/wobbleton/": (200, JOBS), "/grindlewick": (200, LEVER), "/snorvel/": (404, b"")}

        def get(url):
            self.calls.append(url)
            return next((r for key, r in self.table.items() if key in url), (404, b""))
        fx.get = get

    def tearDown(self):
        (wk.BOARDS, wk.WEEKLY, wk.today, fx.PROVIDERS, fx.EXCLUDED, fx.DELAY, fx.RETRY_WAITS, fx.HOST_DELAY, fx.get,
         sent) = self.saved
        fx.SENT.update(sent)
        fx.ROBOTS.clear()
        fx.LAST.clear()
        shutil.rmtree(self.tmp)

    def run_it(self, argv=()):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = wk.main(list(argv))
        return code, out.getvalue()

    def manifest(self, day="2026-11-15"):
        with open(wk.WEEKLY.joinpath(day, "manifest.csv"), newline="", encoding="utf-8") as f:
            return {m["company"]: m for m in csv.DictReader(f)}

    def test_a_read_is_kept_by_its_day_with_each_board_status(self):
        code, out = self.run_it()
        self.assertEqual(code, 0)
        day = wk.WEEKLY.joinpath("2026-11-15")
        self.assertEqual(json.loads(gzip.decompress(day.joinpath("greenhouse_wobbleton.json.gz").read_bytes())),
                         json.loads(JOBS))
        m = self.manifest()
        self.assertEqual((m["Wobbleton Freight"]["status"], m["Wobbleton Freight"]["openings"]), ("ok", "2"))
        self.assertEqual(m["Grindlewick Health"]["status"], "ok")
        self.assertEqual(m["Snorvel Energy"]["status"], "gone")
        with open(wk.WEEKLY.joinpath("reads.csv"), newline="", encoding="utf-8") as f:
            line = list(csv.DictReader(f))[-1]
        self.assertEqual((line["day"], line["ok"], line["gone"], line["postings"], line["left_out"]),
                         ("2026-11-15", "2", "1", "3", "1"))

    def test_a_company_on_the_list_is_never_asked_and_never_named(self):
        code, out = self.run_it()
        self.assertFalse(any("quorvex" in c for c in self.calls))
        self.assertNotIn("Quorvex", out)
        self.assertNotIn("Quorvex Holdings", self.manifest())

    def test_a_company_the_list_names_later_leaves_every_earlier_read(self):
        early = wk.WEEKLY.joinpath("2026-11-08")
        early.mkdir(parents=True)
        early.joinpath("greenhouse_wobbleton.json.gz").write_bytes(gzip.compress(JOBS))
        wk.write_manifest(early, [{"company": "Wobbleton Freight", "provider": "greenhouse", "token": "wobbleton",
                                   "status": "ok", "openings": "2", "bytes": "9", "fetched_at": "t"}])
        self.excluded.write_text("# made up\nQuorvex Holdings\nWobbleton Freight\n", encoding="utf-8")
        code, out = self.run_it()
        self.assertFalse(early.joinpath("greenhouse_wobbleton.json.gz").exists())
        self.assertEqual(wk.read_manifest(early), {})
        self.assertNotIn("Wobbleton", out)

    def test_a_stale_list_stops_the_read(self):
        old = time.time() - 2 * 86400
        os.utime(self.excluded, (old, old))
        with self.assertRaises(SystemExit):
            self.run_it()
        self.assertEqual(self.calls, [])

    def test_a_stopped_read_resumes_and_asks_again_only_what_failed(self):
        self.table["/grindlewick"] = (503, b"")
        self.run_it()
        self.assertEqual(self.manifest()["Grindlewick Health"]["status"], "error")
        self.calls.clear()
        self.table["/grindlewick"] = (200, LEVER)
        self.run_it()
        asked = [c for c in self.calls if not c.endswith("/robots.txt")]
        self.assertEqual(len(asked), 1)
        self.assertIn("grindlewick", asked[0])
        self.assertEqual(self.manifest()["Grindlewick Health"]["status"], "ok")

    def test_the_dry_run_sends_nothing(self):
        code, out = self.run_it(["--dry-run"])
        self.assertEqual((code, self.calls), (0, []))
        self.assertIn("3 requests for 3 boards", out)


if __name__ == "__main__":
    unittest.main()
