"""engine/domains.py on made-up companies: the registrable domain, the hosts that never count, the name match, and the
pick with its confidence, including the unmatched account that stays unmatched instead of guessed."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import domains as dm  # noqa: E402


def gh(url, content=""):
    return {"absolute_url": url, "content": content}


class Domains(unittest.TestCase):
    def test_the_registrable_domain(self):
        self.assertEqual(dm.registrable("www.careers.wobbleton.com"), "wobbleton.com")
        self.assertEqual(dm.registrable("shop.wobbleton.co.uk"), "wobbleton.co.uk")
        self.assertEqual(dm.registrable("localhost"), "")

    def test_hosts_that_never_count(self):
        for host in ("greenhouse.io", "linkedin.com", "uscis.gov", "state.edu", "0.40", "bit.ly"):
            self.assertFalse(dm.counts(host), host)
        self.assertTrue(dm.counts("wobbleton.com"))

    def test_the_name_match(self):
        self.assertTrue(dm.name_match("wobbletonfreight.com", "Wobbleton Freight"))
        self.assertTrue(dm.name_match("getwobbleton.com", "Wobbleton"))
        self.assertTrue(dm.name_match("snrv.io", "Snorvel Energy", token="snrv"))
        self.assertFalse(dm.name_match("snorvel.com", "Wobbleton Freight"))

    def test_a_board_on_the_companys_own_careers_site_wins(self):
        jobs = [gh("https://careers.wobbleton.com/jobs?gh_jid=1",
                   "&lt;a href=&quot;https://www.examplejobs.com/x&quot;&gt;apply&lt;/a&gt;"),
                gh("https://careers.wobbleton.com/jobs?gh_jid=2")]
        domain, confidence, matched, c = dm.pick("Wobbleton Freight", "wobbleton", dm.evidence("greenhouse", jobs))
        self.assertEqual((domain, confidence, matched, c["own_host"]), ("wobbleton.com", "high", True, 2))

    def test_a_third_party_link_alone_stays_unmatched(self):
        jobs = [gh("https://job-boards.greenhouse.io/snorvel/jobs/1",
                   "&lt;a href=&quot;https://www.examplejobs.com/x&quot;&gt;more jobs&lt;/a&gt;")]
        self.assertEqual(dm.pick("Snorvel Energy", "snorvel", dm.evidence("greenhouse", jobs))[:2], ("", "unmatched"))

    def test_one_posting_that_names_the_domain_is_medium(self):
        jobs = [{"description": "<p>Learn more at grindlewick.io today.</p>", "lists": [], "additional": ""}]
        self.assertEqual(dm.pick("Grindlewick Health", "grindlewick", dm.evidence("lever", jobs))[:2],
                         ("grindlewick.io", "medium"))


if __name__ == "__main__":
    unittest.main()
