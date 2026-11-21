"""Location strings as the three providers write them, read against a tiny Gazetteer index of real places."""
import unittest
from pathlib import Path

from engine import boards, locations as L

FIXTURES = Path(__file__).resolve().parent.joinpath("fixtures", "boards")
PLACES = [("CO", "Denver", 39.7621, -104.8759), ("CO", "Aurora", 39.7083, -104.7237), ("UT", "Salt Lake City", 40.7777,
          -111.9306), ("MA", "Boston", 42.3389, -71.0181), ("NY", "New York", 40.6635, -73.9387), ("TX", "Austin",
          30.3005, -97.7522), ("CA", "San Francisco", 37.7272, -123.0322), ("DC", "Washington", 38.9047, -77.0163),
          ("MO", "St. Louis", 38.6358, -90.2451)]
INDEX = {(s, n.lower()): {"name": n, "state": s, "lat": la, "lon": lo} for s, n, la, lo in PLACES}


def kind(raw):
    return L.part(raw, INDEX)


class Parts(unittest.TestCase):
    def test_cities(self):
        for raw, want in (("Denver, CO", ("Denver", "CO")), ("Salt Lake City, UT", ("Salt Lake City", "UT")),
                          ("San Francisco, California, United States", ("San Francisco", "CA")),
                          ("Hybrid - Austin, TX", ("Austin", "TX")), ("Washington, DC", ("Washington", "DC")),
                          ("NYC", ("New York", "NY")), ("Bay Area", ("San Francisco", "CA")), ("Chicago", None),
                          ("Remote - Denver, CO", ("Denver", "CO")), ("Saint Louis", ("St. Louis", "MO"))):
            got = kind(raw)
            if want is None:
                self.assertEqual(got["kind"], "us", raw)
            else:
                self.assertEqual((got["kind"], got["city"], got["state"]), ("city",) + want, raw)

    def test_remote_and_country(self):
        for raw in ("Remote", "Remote - US", "Remote (United States)", "US Remote", "Remote, USA", "Anywhere in the US"):
            self.assertEqual(kind(raw)["kind"], "remote", raw)
        for raw in ("London, UK", "Toronto, ON", "Remote - Canada", "EMEA", "Berlin", "Dublin, Ireland"):
            self.assertEqual(kind(raw)["kind"], "nonus", raw)
        self.assertEqual(kind("United States")["kind"], "us")
        self.assertEqual(kind("Colorado")["kind"], "us")
        self.assertEqual(kind("Narnia Station")["kind"], "unknown")


class Postings(unittest.TestCase):
    def posts(self, name):
        provider, token = name.split("_", 1)
        return {p["job_id"]: p for p in boards.parse(provider, token, FIXTURES.joinpath(f"{name}.json").read_bytes())}

    def test_each_provider(self):
        gh = self.posts("greenhouse_wobbleton")
        self.assertEqual([(p["city"], p["state"]) for p in L.read(gh["102"], INDEX)],
                         [("Denver", "CO"), ("Salt Lake City", "UT")])
        self.assertEqual(L.read(gh["107"], INDEX), [{"kind": "remote", "city": "", "state": ""}])
        lv = self.posts("lever_grindlewick")
        self.assertEqual([p["city"] for p in L.read(lv["aaaa-1111"], INDEX)], ["Boston", "New York"])
        self.assertEqual(L.read(lv["bbbb-2222"], INDEX)[0]["kind"], "remote")
        ab = self.posts("ashby_snorvel")
        self.assertEqual([p["city"] for p in L.read(ab["dddd-4444"], INDEX)], ["Austin", "Denver"])
        self.assertEqual(L.read(ab["eeee-5555"], INDEX)[0]["kind"], "remote")
        self.assertEqual(L.region_of(L.read(ab["eeee-5555"], INDEX)), "us")

    def test_or_and_slashes_split(self):
        got = L.read({"locations": ["Denver, CO or Remote", "SF / NYC"], "places": []}, INDEX)
        self.assertEqual([(g["kind"], g.get("city", "")) for g in got],
                         [("city", "Denver"), ("remote", ""), ("city", "San Francisco"), ("city", "New York")])


if __name__ == "__main__":
    unittest.main()
