"""The page builds and reads every word from WORDS.md, and the never list and the other demos' names stay out of what
ships."""
import re
import tempfile
import unittest
from pathlib import Path

import build
from app import bundle, never, page, words

HERE = Path(__file__).resolve().parent.parent


class Build(unittest.TestCase):
    def test_the_page_builds_from_words(self):
        # Before the scored run nothing matches today's prompt, so the click-through gets the stand-in's briefs.
        args = ["--quiet"] if bundle.scored_records() else ["--stand-in", "--quiet"]
        self.assertEqual(build.main(args), 0)
        html = HERE.joinpath("site", "index.html").read_text(encoding="utf-8")
        w = words.load()
        self.assertIn(f"<title>{w['page.title']}</title>", html)
        self.assertIn(w["page.footer"].split("{date}")[0], html)
        for name in ("data.js", "code.js"):
            self.assertTrue(HERE.joinpath("site", name).exists())

    def test_no_inline_style_or_script_and_nothing_from_another_site(self):
        html = page.render(words.load(), "2026-11-09")
        self.assertNotIn(" style=", html)
        self.assertNotRegex(html, r"<script[^>]*>[^<]")
        self.assertNotRegex(html, r"src=['\"](https?:)?//")
        # The frame links nowhere off the site but its own canonical address, which a link preview reads. Only the
        # postings and boards the script fills in leave it.
        self.assertEqual(re.findall(r"href=['\"](https?://[^'\"]+)", html), [page.LIVE])
        self.assertIn(f"<meta property='og:image' content='{page.SHARE}'>", html)

    def test_a_missing_word_fails_loudly(self):
        with self.assertRaises(words.MissingWord):
            words.Words({}, {})["page.title"]

    def test_the_foreign_list_catches_another_demos_name(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as d:
            f = Path(d, "x.txt")
            f.write_text("A note about Zephyrine Sensors and its alerts.", encoding="utf-8")
            self.assertTrue(any("another demo" in p for p in never.scan([f], never_words=(), foreign_words=("zephyrine",))))
            self.assertEqual(never.scan([f], never_words=(), foreign_words=("quillon",)), [])

    def test_the_private_lists_load_when_present(self):
        # Both lists stay private, so a clean clone of the public repo has neither and skips this.
        if not HERE.joinpath("config", "foreign_words.txt").exists():
            self.skipTest("the foreign list never ships")
        self.assertGreater(len(never.foreign()), 50)
        if HERE.joinpath("tools", "lint_copy.py").exists():
            self.assertGreater(len(never.words()), 5)

    def test_whole_words_only(self):
        self.assertEqual(never.hits("a category of cats", ["cat"]), [])
        self.assertEqual(never.hits("the cat sat", ["cat"]), ["cat"])
        self.assertTrue(never.clean("a category of cats", never_words=("cat",), foreign_words=()))


if __name__ == "__main__":
    unittest.main()
