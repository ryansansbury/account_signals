"""The three parsers on synthetic boards in each provider's shape: one posting format, the kind of every date, repeats
folded, evergreen and temporary roles marked, structured places kept, and unlisted Ashby jobs skipped."""
import unittest
from datetime import date
from pathlib import Path

from app import never
from engine import boards

FIXTURES = Path(__file__).resolve().parent.joinpath("fixtures", "boards")


def load(name):
    provider, token = name.split("_", 1)
    return boards.parse(provider, token, FIXTURES.joinpath(f"{name}.json").read_bytes())


class Greenhouse(unittest.TestCase):
    def setUp(self):
        self.posts = {p["job_id"]: p for p in load("greenhouse_wobbleton")}

    def test_repeats_fold_into_one_posting_with_both_cities(self):
        self.assertEqual(sorted(self.posts), ["101", "102", "104", "105", "106", "107"])
        self.assertEqual(self.posts["102"]["locations"], ["Denver, CO", "Salt Lake City, UT"])
        self.assertEqual(self.posts["102"]["repeats"], 2)

    def test_every_date_keeps_its_kind(self):
        self.assertEqual((self.posts["101"]["posted"], self.posts["101"]["date_kind"]), (date(2026, 11, 2), "published"))
        self.assertEqual((self.posts["102"]["posted"], self.posts["102"]["date_kind"]), (date(2026, 10, 20), "updated"))

    def test_html_escaped_twice_becomes_sentences(self):
        text = self.posts["101"]["text"]
        self.assertIn("You'll lead our move off spreadsheets to a single CRM this quarter", text)
        self.assertIn("Own pipeline reporting for every region. Partner with Finance", text)
        self.assertNotIn("<", text)
        self.assertNotIn("&lt;", text)

    def test_evergreen_temporary_and_ids(self):
        self.assertTrue(self.posts["104"]["evergreen"])
        self.assertFalse(self.posts["101"]["evergreen"])
        self.assertEqual(self.posts["105"]["employment"], "temporary")
        self.assertEqual(self.posts["101"]["employment"], "")
        self.assertEqual(self.posts["101"]["id"], "greenhouse:wobbleton:101")
        self.assertEqual(self.posts["101"]["company"], "Wobbleton Freight")


class Lever(unittest.TestCase):
    def setUp(self):
        self.posts = {p["job_id"]: p for p in load("lever_grindlewick")}

    def test_fields(self):
        p = self.posts["aaaa-1111"]
        self.assertEqual((p["posted"], p["date_kind"]), (date(2026, 10, 28), "created"))
        self.assertEqual(p["locations"], ["Boston, MA", "New York, NY"])
        self.assertEqual(p["places"], [{"city": "", "region": "", "country": "US"}])
        self.assertIs(p["remote"], False)
        self.assertIn("What you'll do. Lead our HubSpot to Salesforce migration", p["text"])
        self.assertTrue(p["url"].startswith("https://jobs.lever.co/"))

    def test_a_contract_role_is_temporary_and_remote(self):
        p = self.posts["bbbb-2222"]
        self.assertEqual(p["employment"], "temporary")
        self.assertIs(p["remote"], True)


class Ashby(unittest.TestCase):
    def setUp(self):
        self.posts = {p["job_id"]: p for p in load("ashby_snorvel")}

    def test_unlisted_jobs_are_skipped(self):
        self.assertEqual(sorted(self.posts), ["dddd-4444", "eeee-5555"])

    def test_structured_places_and_remote(self):
        p = self.posts["dddd-4444"]
        self.assertEqual(p["places"], [{"city": "Austin", "region": "Texas", "country": "United States"},
                                       {"city": "Denver", "region": "CO", "country": "USA"}])
        self.assertEqual(p["locations"], ["Austin", "Denver"])
        self.assertEqual((p["posted"], p["date_kind"]), (date(2026, 11, 6), "published"))
        self.assertIs(self.posts["eeee-5555"]["remote"], True)
        self.assertIn("Partner with sales leadership on territory planning. Improve forecast accuracy", p["text"])


class Fixtures(unittest.TestCase):
    def test_the_made_up_companies_and_people_are_clear_of_every_list(self):
        text = " ".join(f.read_text(encoding="utf-8") for f in FIXTURES.glob("*.json"))
        self.assertEqual(never.hits(text, never.words()), [])
        self.assertEqual(never.hits(text, never.foreign()), [])


if __name__ == "__main__":
    unittest.main()
