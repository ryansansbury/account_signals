"""Albers USA against the Census Bureau's boundaries: cities across the lower 48 and in both insets land inside their own
states, and a city given the wrong state is caught."""
import unittest

from engine import geo

CITIES = [  # real cities, rounded coordinates
    ("Denver", "CO", 39.74, -104.99), ("Boston", "MA", 42.36, -71.06), ("Austin", "TX", 30.27, -97.74),
    ("Seattle", "WA", 47.61, -122.33), ("Miami", "FL", 25.76, -80.19), ("San Francisco", "CA", 37.77, -122.42),
    ("Salt Lake City", "UT", 40.76, -111.89), ("Washington", "DC", 38.90, -77.04), ("Portland", "ME", 43.66, -70.26),
    ("Anchorage", "AK", 61.22, -149.90), ("Juneau", "AK", 58.30, -134.42), ("Honolulu", "HI", 21.31, -157.86),
    ("Hilo", "HI", 19.71, -155.08),
]


class Projection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.map = geo.Map()

    def test_every_state_is_there(self):
        self.assertEqual(len(self.map.states), 51)
        self.assertTrue(set(geo.STATES.values()) <= set(self.map.states))

    def test_cities_land_inside_their_own_state_including_both_insets(self):
        for city, state, lat, lon in CITIES:
            self.assertIsNotNone(self.map.place(lat, lon, state), f"{city}, {state}")

    def test_the_wrong_state_is_caught(self):
        self.assertIsNone(self.map.place(39.74, -104.99, "UT"))
        self.assertIsNone(self.map.place(61.22, -149.90, "WA"))

    def test_the_frame(self):
        for city, state, lat, lon in CITIES:
            x, y = geo.project(lon, lat, state)
            self.assertTrue(0 <= x <= geo.WIDTH and 0 <= y <= geo.HEIGHT, city)

    def test_paths_are_whole_pixels(self):
        d = geo.path_d(self.map.states["Colorado"])
        self.assertTrue(d.startswith("M") and d.endswith("Z"))
        self.assertNotIn(".", d)


if __name__ == "__main__":
    unittest.main()
