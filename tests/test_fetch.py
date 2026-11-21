"""owner/fetch.py offline, through a fake transport and made-up companies: the host lock, the redirect guard, the size
cap, the request ceiling, the terms gate, the exclusion list before and after a read, and the resume behavior."""
import contextlib
import importlib.util
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
spec = importlib.util.spec_from_file_location("owner_fetch", HERE.joinpath("owner", "fetch.py"))
fx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fx)
ONE_JOB = json.dumps({"jobs": [{"id": "1", "title": "Analyst"}]}).encode()
EMPTY = b'{"jobs": []}'


class FetchRules(unittest.TestCase):
    def setUp(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(dir=scratch))
        seed = self.tmp.joinpath("accounts.csv")
        seed.write_text("company,industry,segment,provider,tokens\n"
                        "Wobbleton Freight,logistics,x,greenhouse,wobbleton\n"
                        "Grindlewick Health,health care,x,lever,grindlewick\n"
                        "Snorvel Energy,energy,x,ashby,snorvel\n"
                        "Flonk,software,x,greenhouse,flonk\n", encoding="utf-8")
        self.providers = self.tmp.joinpath("providers.json")
        self.allow(["greenhouse", "ashby", "lever"])
        self.excluded = self.tmp.joinpath("exclusions.txt")
        self.excluded.write_text("# made up\nFlonk\nQuorvex Holdings\n", encoding="utf-8")
        self.saved = (fx.SEED, fx.RAW, fx.PROVIDERS, fx.EXCLUDED, fx.DELAY, fx.RETRY_WAITS, fx.HOST_DELAY, fx.get,
                      fx.OPENER, fx.time, dict(fx.SENT))
        fx.SEED, fx.RAW, fx.PROVIDERS, fx.EXCLUDED = seed, self.tmp.joinpath("raw"), self.providers, self.excluded
        fx.DELAY, fx.RETRY_WAITS, fx.HOST_DELAY = 0, (0, 0), {}
        fx.SENT["n"] = 0
        fx.ROBOTS.clear()
        fx.LAST.clear()
        self.calls = []

    def tearDown(self):
        (fx.SEED, fx.RAW, fx.PROVIDERS, fx.EXCLUDED, fx.DELAY, fx.RETRY_WAITS, fx.HOST_DELAY, fx.get, fx.OPENER, fx.time,
         sent) = self.saved
        fx.SENT.update(sent)
        fx.ROBOTS.clear()
        fx.LAST.clear()
        shutil.rmtree(self.tmp)

    def api_calls(self):
        return [c for c in self.calls if not c.endswith("/robots.txt")]

    def allow(self, names, checked=None):
        checked = checked or date.today().isoformat()
        self.providers.write_text(json.dumps({"max_age_days": 45, "providers": {
            p: {"allowed": p in names, "checked": checked, "status": "test"} for p in ("greenhouse", "lever", "ashby")}}),
            encoding="utf-8")

    def answer(self, table):
        def get(url):
            self.calls.append(url)
            reply = next((r for key, r in table.items() if key in url), (404, b""))
            if isinstance(reply, BaseException):
                raise reply
            return reply
        fx.get = get

    def run_it(self, argv=()):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = fx.main(list(argv))
        return code, out.getvalue()

    def manifest(self):
        return fx.read_manifest()

    # ---- the network guards
    def test_a_url_off_the_three_hosts_is_refused_before_anything_is_sent(self):
        fx.OPENER = None  # anything that reached the opener would raise here
        for url in ("https://example.com/v1/boards/x/jobs", "http://boards-api.greenhouse.io/v1/boards/x/jobs",
                    "https://boards-api.greenhouse.io.example.com/x"):
            with self.assertRaises(ValueError):
                fx.get(url)

    def test_a_redirect_off_the_three_hosts_is_refused(self):
        h = fx.SameHosts()
        self.assertIsNone(h.redirect_request(None, None, 302, "Moved", {}, "https://example.com/elsewhere"))
        self.assertIsNone(h.redirect_request(None, None, 302, "Moved", {}, "http://api.lever.co/v0/postings/x"))

    def test_an_oversized_body_is_skipped_and_the_ceiling_holds(self):
        class Reply:
            status = 200

            def __init__(self, n):
                self.n = n

            def read(self, k):
                return b"x" * min(self.n, k)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class Opener:
            def __init__(self, n):
                self.n, self.opened = n, 0

            def open(self, req, timeout=None):
                self.opened += 1
                assert req.get_method() == "GET" and req.full_url.startswith("https://")
                return Reply(self.n)

        fx.OPENER = Opener(fx.MAX_BYTES + 10)
        self.assertEqual(fx.get("https://api.lever.co/v0/postings/x?mode=json"), (413, b""))
        fx.OPENER = Opener(10)
        fx.SENT["n"] = fx.CEILING
        with self.assertRaises(fx.Ceiling):
            fx.get("https://api.lever.co/v0/postings/x?mode=json")
        self.assertEqual(fx.OPENER.opened, 0)

    def test_only_the_job_board_paths_are_asked(self):
        fx.OPENER = None
        for url in ("https://boards-api.greenhouse.io/embed/job_board?for=x", "https://api.lever.co/v1/postings/x",
                    "https://api.ashbyhq.com/application.submit"):
            with self.assertRaises(ValueError):
                fx.get(url)
        fx.check_url("https://api.ashbyhq.com/robots.txt")
        fx.check_url("https://boards-api.greenhouse.io/v1/boards/x/jobs?content=true")

    def test_robots_txt_is_read_and_honored(self):
        self.answer({"api.ashbyhq.com/robots.txt": (200, b"User-agent: *\nDisallow: /posting-api/\n"),
                     "api.lever.co/robots.txt": (200, b"User-agent: *\nCrawl-delay: 1\n"),
                     "boards/wobbleton/jobs": (200, ONE_JOB), "postings/grindlewick": (200, b'[{"id": "2"}]')})
        code, out = self.run_it()
        self.assertFalse([c for c in self.api_calls() if "api.ashbyhq.com" in c])
        self.assertIn("ashby:snorvel:robots", self.manifest()["Snorvel Energy"]["tried"])
        self.assertIn("crawl delay 1 s", out)
        self.assertIn("boards-api.greenhouse.io: no robots.txt", out)

    def test_a_host_whose_robots_txt_fails_stays_off(self):
        self.answer({"api.lever.co/robots.txt": (503, b""), "boards/wobbleton/jobs": (200, ONE_JOB),
                     "job-board/snorvel": (200, ONE_JOB)})
        self.run_it()
        self.assertFalse([c for c in self.api_calls() if "api.lever.co" in c])

    def test_the_pace_follows_lever_and_any_crawl_delay(self):
        clock = {"t": 1000.0, "slept": []}

        class Clock:
            @staticmethod
            def time():
                return clock["t"]

            @staticmethod
            def sleep(s):
                clock["slept"].append(round(s, 3))
                clock["t"] += s

        fx.time = Clock
        fx.DELAY, fx.HOST_DELAY = 0.4, {"api.lever.co": 1.1}
        for _ in range(2):
            fx.pace("api.lever.co")
        self.assertEqual(clock["slept"], [1.1])
        rp = fx.urllib.robotparser.RobotFileParser()
        rp.parse(["User-agent: *", "Crawl-delay: 3"])
        fx.ROBOTS["api.ashbyhq.com"] = rp
        for _ in range(2):
            fx.pace("api.ashbyhq.com")
        self.assertEqual(clock["slept"], [1.1, 3.0])

    def test_a_rate_limit_is_retried_twice_and_a_server_error_once(self):
        class Fail:
            def __init__(self, code):
                self.code, self.opened = code, 0

            def open(self, req, timeout=None):
                self.opened += 1
                raise fx.urllib.error.HTTPError(req.full_url, self.code, "x", {}, None)

        fx.OPENER = Fail(429)
        self.assertEqual(fx.get("https://api.lever.co/v0/postings/x?mode=json"), (429, b""))
        self.assertEqual(fx.OPENER.opened, 3)
        fx.OPENER = Fail(503)
        self.assertEqual(fx.get("https://api.lever.co/v0/postings/x?mode=json"), (503, b""))
        self.assertEqual(fx.OPENER.opened, 2)

    # ---- the gates
    def test_no_allowed_provider_means_no_request(self):
        self.allow([])
        self.answer({})
        code, out = self.run_it()
        self.assertEqual(code, 1)
        self.assertEqual(self.calls, [])

    def test_stale_terms_turn_a_provider_off(self):
        self.allow(["greenhouse", "lever"], checked="2026-01-01")
        names, notes = fx.allowed_providers(self.providers, today=date(2026, 11, 9))
        self.assertEqual(names, [])
        self.assertEqual(sum("days ago" in n for n in notes), 2)
        self.assertEqual(fx.allowed_providers(self.providers, today=date(2026, 1, 20))[0], ["greenhouse", "lever"])

    def test_a_missing_or_old_exclusion_list_stops_the_run(self):
        self.excluded.unlink()
        self.answer({})
        with self.assertRaises(SystemExit):
            self.run_it()
        self.excluded.write_text("Flonk\n", encoding="utf-8")
        old = time.time() - 9 * 86400
        os.utime(self.excluded, (old, old))
        with self.assertRaises(SystemExit):
            self.run_it()
        self.assertEqual(self.calls, [])

    def test_an_excluded_company_is_never_requested_or_named(self):
        self.answer({"boards/wobbleton/jobs": (200, ONE_JOB), "postings/grindlewick": (200, b'[{"id": "2"}]'),
                     "job-board/snorvel": (200, ONE_JOB)})
        code, out = self.run_it()
        self.assertEqual(code, 0)
        self.assertFalse(any("flonk" in c.lower() for c in self.calls), self.calls)
        self.assertNotIn("flonk", out.lower())
        self.assertNotIn("Flonk", self.manifest())
        code, out = self.run_it(["--dry-run"])
        self.assertNotIn("flonk", out.lower())

    def test_a_board_whose_own_name_is_excluded_is_deleted_and_never_named(self):
        self.answer({"boards/wobbleton/jobs": (200, ONE_JOB), "v1/boards/wobbleton": (200, b'{"name": "Quorvex Holdings"}'),
                     "postings/grindlewick": (200, b'[{"id": "2"}]'), "job-board/snorvel": (200, ONE_JOB)})
        code, out = self.run_it()
        m = self.manifest()["Wobbleton Freight"]
        self.assertEqual((m["status"], m["provider"], m["board_name"]), ("dropped", "", ""))
        self.assertFalse(fx.RAW.joinpath("boards", "greenhouse_wobbleton.json").exists())
        self.assertNotIn("quorvex", out.lower())

    def test_a_company_excluded_after_a_read_is_purged_on_the_next_run(self):
        self.answer({"boards/wobbleton/jobs": (200, ONE_JOB), "postings/grindlewick": (200, b'[{"id": "2"}]'),
                     "job-board/snorvel": (200, ONE_JOB)})
        self.run_it()
        self.assertTrue(fx.RAW.joinpath("boards", "lever_grindlewick.json").exists())
        self.excluded.write_text("Flonk\nGrindlewick Health\n", encoding="utf-8")
        self.run_it()
        self.assertFalse(fx.RAW.joinpath("boards", "lever_grindlewick.json").exists())
        self.assertNotIn("Grindlewick Health", self.manifest())

    # ---- resume
    def test_an_empty_board_does_not_end_the_search(self):
        self.answer({"boards/wobbleton/jobs": (200, EMPTY), "job-board/wobbleton": (200, ONE_JOB)})
        self.run_it()
        m = self.manifest()["Wobbleton Freight"]
        self.assertEqual((m["provider"], m["openings"]), ("ashby", "1"))

    def test_a_rerun_asks_only_about_network_errors(self):
        self.answer({"boards/wobbleton/jobs": (200, ONE_JOB), "postings/grindlewick": (0, b"timed out"),
                     "boards/grindlewick": (0, b"timed out"), "job-board/grindlewick": (0, b"timed out"),
                     "job-board/snorvel": (200, ONE_JOB)})
        self.run_it()
        self.calls.clear()
        self.run_it()
        self.assertTrue(self.calls)
        self.assertTrue(all("grindlewick" in c for c in self.api_calls()), self.calls)

    def test_an_interrupted_run_keeps_every_row(self):
        self.answer({"boards/wobbleton/jobs": (200, ONE_JOB), "postings/grindlewick": (0, b"timed out"),
                     "boards/grindlewick": (0, b"timed out"), "job-board/grindlewick": (0, b"timed out"),
                     "job-board/snorvel": (200, ONE_JOB)})
        self.run_it()
        before = self.manifest()
        self.answer({"grindlewick": KeyboardInterrupt()})
        with self.assertRaises(KeyboardInterrupt), contextlib.redirect_stdout(io.StringIO()):
            fx.main([])
        self.assertEqual(self.manifest(), before)

    def test_the_ceiling_saves_the_manifest_and_stops(self):
        def get(url):
            raise fx.Ceiling()
        fx.get = get
        code, out = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("ceiling", out)


if __name__ == "__main__":
    unittest.main()
