"""Redaction on made-up people: each layer, names inside runs of title words, and the business phrases, places and tools
that must survive."""
import unittest

from engine import redact as R

PLACES = ("Ann Arbor", "Fort Collins", "Salt Lake City", "Santa Clara", "San Luis Obispo")


class Layers(unittest.TestCase):
    def setUp(self):
        self.r = R.Redactor(places=PLACES)

    def clean(self, text, keep=()):
        return self.r.redact(text, keep)

    def test_emails_phones_links_handles_and_recruiter_tags(self):
        text, n = self.clean("Write to marisol.q@wobbleton.example or call (303) 555-0142 or +44 20 7946 0958. "
                             "Follow @wobbleton_jobs and see https://wobbleton.example/careers or "
                             "linkedin.com/in/someone-made-up #LI-MQ1 #LI-Remote")
        for raw in ("@wobbleton.example", "555-0142", "7946", "@wobbleton_jobs", "https://", "linkedin.com/in", "#LI"):
            self.assertNotIn(raw, text)
        self.assertEqual((n["email"], n["phone"], n["handle"], n["link"], n["tag"]), (1, 2, 1, 2, 2))

    def test_a_tool_written_as_a_bare_domain_stays(self):
        self.assertEqual(self.clean("Experience with Salesforce.com and HubSpot is a plus.")[0],
                         "Experience with Salesforce.com and HubSpot is a plus.")

    def test_names_after_cues_and_titles(self):
        cases = {
            "Questions? Contact Marisol Quentworth at the office.": "Questions? Contact [name removed] at the office.",
            "You'll report to our CRO, Dashiell Prunkworth.": "You'll report to our CRO, [name removed].",
            "This role reports directly to Priya.": "This role reports directly to [name removed].",
            "You'll be led by our VP of Sales, Odalys Brinkerhoff, from day one.":
                "You'll be led by our VP of Sales, [name removed], from day one.",
            "Your recruiter is Tobiah Wexcombe.": "Your recruiter is [name removed].",
        }
        for raw, want in cases.items():
            self.assertEqual(self.clean(raw)[0], want, raw)

    def test_a_name_inside_a_run_of_title_words(self):
        text, n = self.clean("Senior Revenue Operations Manager Jane Q. Quentworth will train you.")
        self.assertEqual(text, "Senior Revenue Operations Manager [name removed] will train you.")
        self.assertEqual(n["name"], 1)
        self.assertEqual(self.clean("Meet Tobiah Smith and Lorna Higgins this week.")[0],
                         "Meet [name removed] and [name removed] this week.")

    def test_business_phrases_places_and_tools_survive(self):
        for keep in ("Lead our HubSpot to Salesforce migration with Revenue Operations and Finance.",
                     "Work closely with Sales, Marketing, and Customer Success.",
                     "Offices in New York, Salt Lake City, Fort Collins, Santa Clara, and Ann Arbor.",
                     "Head of Sales, North America", "Manager, Revenue Operations", "Our Series B closed in May.",
                     "Partner with Chili Piper, Clay, and Gong admins.", "Account Executive, Mid-Market",
                     "Expanding across New England and the Pacific Northwest.",
                     "A new office in San Luis Obispo."):
            self.assertEqual(self.clean(keep)[0], keep, keep)

    def test_the_accounts_own_name_is_never_a_person(self):
        raw = "Morgan Quentworth Freight is growing."
        self.assertEqual(self.clean(raw, keep=["Morgan Quentworth Freight"])[0], raw)
        self.assertEqual(self.clean(raw)[0], "[name removed] Freight is growing.")

    def test_camel_case_products_are_never_split(self):
        self.assertEqual(self.clean("Admins for HubSpot Sales Hub and LeanData Router.")[0],
                         "Admins for HubSpot Sales Hub and LeanData Router.")


if __name__ == "__main__":
    unittest.main()
