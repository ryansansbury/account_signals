"""The exclusion matcher, on made-up names only: normalizing, matching, mentions in text, the tool exception (D6), and
reports that give counts and never a name."""
import tempfile
import unittest
from pathlib import Path

from app import never
from engine import exclusions as X

HERE = Path(__file__).resolve().parent.parent
NAMES = ["The Quorvex Company, Inc.", "Zarnoth Labs", "Plinth & Moor LLC", "Vexley", "Brimble", "Flonk",
         "Glimmerbase", "Qx", "7Zonquil", "Snorvel (via a recruiter)"]


class Names(unittest.TestCase):
    def test_the_made_up_names_are_clear_of_every_list(self):
        text = " | ".join(NAMES)
        self.assertEqual(never.hits(text, never.words()), [])
        self.assertEqual(never.hits(text, never.foreign()), [])


class Normalizing(unittest.TestCase):
    def test_full_names(self):
        self.assertEqual(X.full("The Quorvex Company, Inc."), "quorvex")
        self.assertEqual(X.full("Plinth & Moor LLC"), "plinth and moor")
        self.assertEqual(X.full("Snorvel (via a recruiter)"), "snorvel")
        self.assertEqual(X.full("Café Wobblet, Corp."), "cafe wobblet")
        self.assertEqual(X.full("Wobblet's Pantry"), "wobblets pantry")

    def test_cores_drop_generic_words_but_never_the_last_one(self):
        self.assertEqual(X.core("Zarnoth Labs"), "zarnoth")
        self.assertEqual(X.core("Zarnoth Technologies Inc"), "zarnoth")
        self.assertEqual(X.core("Labs"), "labs")


class Matching(unittest.TestCase):
    def setUp(self):
        self.ex = X.Exclusions(NAMES)

    def test_the_same_company_written_differently(self):
        for n in ("Quorvex", "QUORVEX INC", "quorvex, inc.", "The Quorvex Co.", "Zarnoth", "Zarnoth AI",
                  "Zarnoth Technologies", "Plinth and Moor", "Plinth Moor", "Plinth & Moor Corp", "Snorvel"):
            self.assertTrue(self.ex.matches(n), n)

    def test_a_longer_name_that_starts_with_an_excluded_one(self):
        self.assertTrue(self.ex.matches("Vexley Quarrow"))
        self.assertTrue(self.ex.matches("Brimble Freight"))

    def test_part_of_a_word_is_not_a_match(self):
        self.assertFalse(self.ex.matches("Brimblecombe"))
        self.assertFalse(self.ex.matches("Vexleyton Health"))

    def test_a_short_name_matches_only_itself(self):
        self.assertTrue(self.ex.matches("Qx"))
        self.assertFalse(self.ex.matches("Qx Freight"))

    def test_a_board_token(self):
        self.assertTrue(self.ex.matches("Something Else Entirely", ["quorvex"]))
        self.assertTrue(self.ex.matches("Something Else Entirely", ["plinthmoor"]))
        self.assertFalse(self.ex.matches("Something Else Entirely", ["wobbleton"]))

    def test_unrelated_companies_stay(self):
        for n in ("Wobbleton Freight", "Grindlewick Health", "Moor Plinth"):
            self.assertFalse(self.ex.matches(n), n)

    def test_keep_returns_the_rest_and_a_count(self):
        rows = [{"company": "Quorvex Inc"}, {"company": "Wobbleton Freight"}, {"company": "Other", "tokens": "flonk"}]
        kept, dropped = self.ex.keep(rows)
        self.assertEqual([r["company"] for r in kept], ["Wobbleton Freight"])
        self.assertEqual(dropped, 2)


class Mentions(unittest.TestCase):
    def setUp(self):
        self.ex = X.Exclusions(NAMES, tools=["Glimmerbase"])

    def test_a_proper_noun_counts_and_a_common_word_does_not(self):
        self.assertEqual(self.ex.mentions("Our team works in Flonk every day."), 1)
        self.assertEqual(self.ex.mentions("we flonk the numbers every week"), 0)
        self.assertEqual(self.ex.mentions("Flonk-certified admins and a 7Zonquil partner"), 2)
        self.assertEqual(self.ex.mentions("Plinth & Moor and Quorvex, and then Plinth Moor"), 3)

    def test_a_tool_on_the_list_is_set_aside_in_text_but_never_as_an_account(self):
        self.assertEqual(self.ex.mentions("Lead the Glimmerbase migration."), 0)
        self.assertTrue(self.ex.matches("Glimmerbase"))
        self.assertEqual(X.Exclusions(NAMES).mentions("Lead the Glimmerbase migration."), 1)

    def test_part_of_a_word_is_not_a_mention(self):
        self.assertEqual(self.ex.mentions("Brimblecombe and Quorvexian"), 0)


class Files(unittest.TestCase):
    def test_a_missing_list_is_empty_and_marked_absent(self):
        ex = X.load(HERE.joinpath(".cache", "tmp", "no-such-list.txt"))
        self.assertFalse(ex.present)
        self.assertEqual(len(ex), 0)
        self.assertFalse(ex.matches("Quorvex"))

    def test_the_scan_gives_a_count_and_never_the_name(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as d:
            listed = Path(d, "list.txt")
            listed.write_text("# made-up list\n" + "\n".join(NAMES) + "\n", encoding="utf-8")
            page = Path(d, "page.txt")
            page.write_text("Quorvex is hiring, and so is Zarnoth.", encoding="utf-8")
            problems = X.scan([page], X.load(listed, Path(d, "no-tools.txt")))
            self.assertEqual(problems, ["page.txt names a company on the private exclusion list 2 time(s)"])
            self.assertFalse(any(n.split()[0].lower() in problems[0].lower() for n in ("Quorvex", "Zarnoth")))


class NameMentions(unittest.TestCase):
    def test_an_account_whose_name_mentions_one_on_the_list_is_left_out(self):
        ex = X.Exclusions(["Zorb"])
        self.assertTrue(ex.matches("Big Zorb Freight"))
        self.assertFalse(ex.matches("Zorbular Freight"))
        kept, gone = ex.keep([{"company": "Big Zorb Freight"}, {"company": "Quillon Freight"}])
        self.assertEqual(([r["company"] for r in kept], gone), (["Quillon Freight"], 1))


class Places(unittest.TestCase):
    def test_a_region_is_a_place_and_the_word_alone_still_counts(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "exclusions.txt")
            path.write_text("Central Co\n", encoding="utf-8")
            ex = X.load(path)
        self.assertIn("Central Coast", X.read_names(X.PLACES))
        self.assertEqual(ex.mentions("Our reps cover the Central Coast and the valley."), 0)
        self.assertEqual(ex.mentions("Central signed a three year deal."), 1)


if __name__ == "__main__":
    unittest.main()
