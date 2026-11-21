"""The Gazetteer reader on both layouts the Census Bureau has used (tabs through 2024, pipes from 2025), with a byte
order mark, legal suffixes and consolidated city names."""
import tempfile
import unittest
from pathlib import Path

from engine import gazetteer

HERE = Path(__file__).resolve().parent.parent
COLS = ["USPS", "GEOID", "GEOIDFQ", "ANSICODE", "NAME", "LSAD", "FUNCSTAT", "ALAND", "AWATER", "ALAND_SQMI",
        "AWATER_SQMI", "INTPTLAT", "INTPTLONG"]
ROWS = [["CO", "0820000", "x", "x", "Denver city", "25", "A", "396000000", "1", "1", "1", "39.762", "-104.876"],
        ["CO", "0835000", "x", "x", "Highlands Ranch CDP", "57", "S", "62000000", "1", "1", "1", "39.553", "-104.969"],
        ["TN", "4752006", "x", "x", "Nashville-Davidson metropolitan government (balance)", "00", "F", "1300000000",
         "1", "1", "1", "36.171", "-86.785"],
        ["HI", "1571550", "x", "x", "Urban Honolulu CDP", "57", "S", "156000000", "1", "1", "1", "21.325", "-157.845"]]


class Gazetteer(unittest.TestCase):
    def write(self, d, sep, bom=False):
        lines = [sep.join(COLS)] + [sep.join(r) for r in ROWS]
        p = Path(d, "2025_Gaz_place_national.txt")
        p.write_text(("\ufeff" if bom else "") + "\n".join(lines) + "\n", encoding="utf-8")
        return p

    def test_tabs_pipes_and_a_byte_order_mark(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        for sep, bom in (("\t", False), ("|", False), ("|", True)):
            with tempfile.TemporaryDirectory(dir=scratch) as d:
                places = gazetteer.read(self.write(d, sep, bom))
                index = gazetteer.index(places)
                self.assertEqual(index[("CO", "denver")]["lat"], 39.762)
                self.assertIn(("CO", "highlands ranch"), index)
                self.assertIn(("TN", "nashville"), index)
                self.assertIn(("HI", "honolulu"), index)
                self.assertEqual(gazetteer.find(d).name, "2025_Gaz_place_national.txt")


if __name__ == "__main__":
    unittest.main()
