"""The claim checker's answers, pinned by hand. The vectors prove the JavaScript matches the Python, and these prove the
Python is right: supported claims pass and each kind of unsupported claim is caught."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE.joinpath("tests")))

import make_vectors as mv  # noqa: E402
from engine import claims  # noqa: E402

WANT = {
    "Wobbleton Freight posted three revenue and sales operations roles in the last 30 days [1][2][3].": [],
    "It posted five operations roles this week [1][2].": ["recency: this week", "number: five"],
    "Their CRO, Jordan Blake, wants a new CRM [1].": ["name: Jordan", "name: Blake"],
    "Maria leads revenue operations there [1].": ["name: Maria"],
    "They run Gong across the team [5].": ["tool: Gong"],
    "They're moving from HubSpot to Salesforce [5].": [],
    "Wobbleton Freight has 48 open roles, mostly in Denver [0].": [],
    "The first role was posted November 6 [1].": ["date: November 6"],
    "It has been hiring since November [1][2].": ["date: since November"],
    "This cites a source that isn't there [9].": ["cite: [9]", "cite: none"],
    'They want "a unified CRM by spring" [4].': ['quote: "a unified CRM by spring"'],
    "Their [name removed] is leading it [1].": ["rule: a redaction marker"],
    "A $150K budget sits behind the 48 open roles [0].": ["number: $150K"],
    "Wobbleton Freight had 48 open roles on its public job board on 2026-11-09 [0].": [],
    "The first role was published 2026-11-05 [1].": [],
    "The first role was published 2026-11-04 [1].": ["date: 2026-11-04"],
    'The team says it is moving "off spreadsheets to a single CRM this quarter." [4]': [],
    "Wobbleton Freight's board lists a \"Revenue Operations Manager\" role [1].": [],
    "Is that one of your priorities this year [1]?": [],
    "One posting went up this week [1].": [],
    "Four postings went up this week [1].": ["number: Four"],
    "Sales hiring shows up in more than one posting [2][3].": [],
    "The newest posting was 4 days old on the read date [1].": [],
    "That posting went up 20 days before the read date [3].": [],
    "That posting went up 21 days before the read date [3].": ["recency: 21 days before the read date"],
    "Wobbleton Freight had 48 open roles on its public job board on 2026-11-09 [0]. Most of them were in Denver [0].": [],
    "The CRM-related postings point to a cleanup [1][4].": [],
    "The Zorblat-based team is hiring [1].": ["name: Zorblat-based"],
    "Wobbleton Freight listed 48 open roles on November 9 [0].": [],
    "The first role was published November 9 [1].": ["date: November 9"],
    "Two postings went up in the 20 days before that read date [1][3].": [],
    "Two postings went up in the 10 days before the read date [1][3].": ["recency: in the 10 days before the read date"],
    "The Revenue Operations Manager role went up in November [1].": [],
    "The Revenue Operations Manager role went up in October [1].": ["date: in October"],
    "Postings went up in October and in November [1][2].": [],
    "The posting from July 2026 is still open [1].": ["date: from July"],
}


class Claims(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src, cls.tools, cls.fn = mv.claim_sources(), claims.load_tools(), claims.load_first_names()

    def check(self, text):
        cites = [int(c) for c in claims.MARK.findall(text)]
        return claims.check_sentence(text, cites, self.src, mv.ACCOUNT, mv.READ_ON, self.tools, first_names=self.fn)

    def test_each_kind_of_claim(self):
        for text, want in WANT.items():
            self.assertEqual(self.check(text), want, text)

    def test_a_quote_carries_its_own_dates(self):
        text = 'A posting from 4 days ago says the team is moving "off spreadsheets to a single CRM this quarter" [4].'
        self.assertEqual(self.check(text), [])

    def test_the_first_touch_rules_and_promises(self):
        good, bad = mv.TOUCHES[2], mv.TOUCHES[1]
        self.assertEqual(claims.check_touch(good, self.src, mv.ACCOUNT, mv.READ_ON, self.tools, self.fn), [])
        problems = claims.check_touch(bad, self.src, mv.ACCOUNT, mv.READ_ON, self.tools, self.fn)
        for p in ("rule: greeting", "rule: sign-off", "rule: an unknown placeholder", "cite: none"):
            self.assertIn(p, problems)
        promised = claims.check_touch(mv.TOUCHES[0], self.src, mv.ACCOUNT, mv.READ_ON, self.tools, self.fn)
        self.assertIn("promise: guarantee", promised)
        self.assertIn("promise: free", promised)

    def test_a_first_touch_pools_its_cites_for_recency(self):
        # The email cites a posting from 4 days ago and one from 69 days ago. "In the last week" holds for the first,
        # which is enough in an email, while a brief sentence citing both would need both inside the week.
        pooled = mv.TOUCHES[3]
        self.assertEqual(claims.check_touch(pooled, self.src, mv.ACCOUNT, mv.READ_ON, self.tools, self.fn), [])
        line = "Your team posted a Revenue Operations Manager role in the last week [1][5]."
        self.assertEqual(self.check(line), ["recency: in the last week"])

    def test_a_whole_brief(self):
        ok = claims.check_brief(mv.BRIEFS[0], self.src, mv.ACCOUNT, mv.READ_ON, self.tools, first_names=self.fn)
        self.assertTrue(ok["ok"], ok)
        bad = claims.check_brief(mv.BRIEFS[1], self.src, mv.ACCOUNT, mv.READ_ON, self.tools, first_names=self.fn)
        self.assertFalse(bad["ok"])
        self.assertIn("rule: three questions", bad["problems"])


if __name__ == "__main__":
    unittest.main()
