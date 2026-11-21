"""The personal-data scan on made-up text: it finds what redaction would have removed, allows the job board links and
this project's own, never prints what it found, and leaves stylesheets alone."""
import tempfile
import unittest
from pathlib import Path

from engine import privacy

HERE = Path(__file__).resolve().parent.parent


class Privacy(unittest.TestCase):
    def test_it_finds_each_kind(self):
        text = ("one marisol.q@wobbleton.example\ntwo 303-555-0142\nthree https://example.com/x\n"
                "four @wobbleton_jobs\nfive Contact Lorna Higgins today")
        found = privacy.findings(text)
        self.assertEqual(found, {"email": [1], "phone": [2], "link": [3], "handle": [4], "name": [5]})

    def test_allowed_links_and_redacted_text_pass(self):
        text = ("https://job-boards.greenhouse.io/wobbleton/jobs/101 https://jobs.lever.co/grindlewick/aaaa-1111\n"
                "https://jobs.ashbyhq.com/snorvel/dddd-4444 https://www.ryansansbury.com/account-signals/\n"
                "https://github.com/ryansansbury/account_signals https://www.linkedin.com/in/ryansansbury\n"
                "Questions? Contact [name removed] at [email removed]. Built by Ryan Sansbury.\n"
                "Revenue Operations Manager in Salt Lake City")
        self.assertEqual(privacy.findings(text), {})
        self.assertEqual(privacy.findings("https://www.linkedin.com/in/someone-else"), {"link": [1]})

    def test_a_postings_own_url_is_allowed_and_nothing_else_on_its_host(self):
        own = "https://careers.wobbleton.example/jobs/101?gh_jid=101"
        self.assertEqual(privacy.findings(own, allowed_urls={own}), {})
        self.assertEqual(privacy.findings("https://careers.wobbleton.example/team/someone", allowed_urls={own}),
                         {"link": [1]})

    def test_a_city_that_holds_a_first_name_is_a_place(self):
        from engine import redact
        r = redact.Redactor(places=("San Luis Obispo",))
        self.assertEqual(privacy.findings("city San Luis Obispo", redactor=r), {})

    def test_an_accounts_own_name_is_kept(self):
        self.assertEqual(privacy.findings("Jackson Higgins Freight", keep=["Jackson Higgins Freight"]), {})

    def test_a_stylesheet_is_checked_for_emails_and_links_only(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as d:
            css = Path(d, "app.css")
            css.write_text("@media (max-width: 600px) { .x { color: red } }\n@font-face { font-family: Inter }\n",
                           encoding="utf-8")
            data = Path(d, "notes.md")
            data.write_text("Ask Lorna Higgins.\n", encoding="utf-8")
            problems = privacy.scan([css, data])
            self.assertEqual(problems, ["notes.md may hold a person's details: 1 name line(s) (first at line 1)"])
            self.assertNotIn("Higgins", problems[0])


if __name__ == "__main__":
    unittest.main()
