"""The code section shows excerpts of the real files: every line as it stands in its file under its own number, never a
whole file, and a name that's gone from its file stops the build."""
import tempfile
import unittest
from pathlib import Path

from app import code_view, words

HERE = Path(__file__).resolve().parent.parent
SAMPLE = '''"""A made-up module for the test."""
import math


def kept(x):
    return math.sqrt(x)


def skipped(y):
    return y * 2


def also_kept(z):
    return z + 1
'''


class CodeView(unittest.TestCase):
    def test_every_excerpt_matches_its_file_line_for_line(self):
        for rel, f in code_view.collect().items():
            lines = HERE.joinpath(*rel.split("/")).read_text(encoding="utf-8").splitlines()
            self.assertEqual(f["lines"], len(lines), rel)
            for start, text in f["parts"]:
                got = text.split("\n")
                self.assertEqual(got, lines[start - 1:start - 1 + len(got)], f"{rel} at line {start}")

    def test_no_file_goes_in_whole(self):
        for rel, f in code_view.collect().items():
            shown = sum(len(t.split("\n")) for _, t in f["parts"])
            self.assertLess(shown, f["lines"], rel)

    def test_the_featured_files_all_have_excerpts(self):
        featured = words.load().table("ui.how.code.files")
        self.assertTrue(set(featured) <= set(code_view.collect(featured)))
        self.assertIn(code_view.DEFAULT, code_view.EXCERPTS)

    def test_neighbors_join_and_a_skip_splits(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "pkg").mkdir()
            Path(tmp, "pkg", "sample.py").write_text(SAMPLE, encoding="utf-8")
            f = code_view.excerpt("pkg/sample.py", ("kept", "also_kept"), root=tmp)
            self.assertEqual([p[0] for p in f["parts"]], [1, 5, 13])
            self.assertTrue(f["parts"][1][1].startswith("def kept"))

    def test_a_name_gone_from_its_file_stops_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "pkg").mkdir()
            Path(tmp, "pkg", "sample.py").write_text(SAMPLE, encoding="utf-8")
            with self.assertRaises(ValueError):
                code_view.excerpt("pkg/sample.py", ("kept", "renamed_away"), root=tmp)

    def test_a_whole_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "pkg").mkdir()
            Path(tmp, "pkg", "tiny.py").write_text("def only(x):\n    return x\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                code_view.excerpt("pkg/tiny.py", ("only",), root=tmp)


if __name__ == "__main__":
    unittest.main()
