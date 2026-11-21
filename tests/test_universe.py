"""The seed list filter on made-up candidates: exclusions, the never and foreign lists, repeats and malformed rows, with
counts and never a name."""
import unittest

from engine import exclusions, universe


def row(company, industry="software", provider="greenhouse", tokens=""):
    return {"company": company, "industry": industry, "segment": "x", "provider": provider, "tokens": tokens}


class Universe(unittest.TestCase):
    def test_filters_and_counts(self):
        rows = [row("Wobbleton Freight", "logistics"), row("Quorvex Inc"), row("Quorvex"), row("Zephyrine Grid", "energy"),
                row("Grindlewick Health", "health care"), row("Other Name", tokens="flonk"), row("Wobbleton Freight, Inc.")]
        ex = exclusions.Exclusions(["Quorvex", "Flonk"])
        kept, left = universe.build(rows, ex, never_words=(), foreign_words=("zephyrine",))
        self.assertEqual([r["company"] for r in kept], ["Wobbleton Freight", "Grindlewick Health"])
        self.assertEqual(dict(left), {"repeats": 2, "never or foreign list": 1, "exclusion list": 2})

    def test_a_malformed_row_stops_it(self):
        with self.assertRaises(ValueError):
            universe.build([row("Wobbleton Freight", "aerospace")], exclusions.Exclusions([]), (), ())


if __name__ == "__main__":
    unittest.main()
