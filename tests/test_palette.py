"""The palette passes WCAG contrast in both modes: 4.5 to 1 for every text color on the surface it sits on (the words,
the links, the pills, the tier badges, the verdicts, the banner, the tooltip and the buttons), and 3 to 1 for every mark
on the map against the page behind it. The light page is the default and dark mode (11/20) sets its own values in body.dark.
The colors are read from site/app.css itself, so a change there is checked here."""
import re
import unittest
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent.joinpath("site", "app.css").read_text(encoding="utf-8")


def block(selector):
    """The custom properties a rule sets that are plain colors, as {name: #rrggbb}."""
    start = CSS.index(selector + " {")
    body = CSS[start:CSS.index("}", start)]
    out = {}
    for name, value in re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{3,6})\b", body):
        out[name] = "#" + "".join(c * 2 for c in value[1:]) if len(value) == 4 else value
    return out


light_vars = block(":root")
dark_vars = dict(light_vars, **block("body.dark"))
WHITE, NEAR_BLACK = "#ffffff", "#15110f"


def luminance(hex_color):
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b, palette):
    a, b = (palette[x[2:]] if x.startswith("--") else x for x in (a, b))
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# Every text color on every surface it's drawn on, in both modes.
TEXT = [(t, s) for t in ("--ink", "--ink2", "--muted") for s in ("--bg", "--panel", "--soft")] + [
    ("--f7", "--bg"), ("--f7", "--panel"), ("--f7", "--f1"), ("--f7", "--soft"),
    ("--ink2", "--tint-c"), ("--muted", "--tint-d"), ("--muted", "--code-bg"), ("--ink", "--code-bg"),
    ("--ok", "--okb"), ("--warn", "--warnb"), ("--bad", "--badb"), ("--ok", "--bg"), ("--bad", "--bg"),
    ("--bn-ink", "--bn"), ("--tip-ink", "--tip"), (WHITE, "--f"), (WHITE, "--tour"), ("--bg", "--ink")]
# The badges set their own text color in each mode.
BADGES = {"light": [(WHITE, "--tA"), ("--f7", "--f2")], "dark": [(NEAR_BLACK, "--tA"), ("#fed7aa", "--f2")]}
# The map's marks that have to stand out against the page: tier A, the hot thread and the selected ring's outline. Tiers
# B to D run on purpose from orange to a pale dot, and each tier also shows as its letter in the lists and the card, so
# color is never the only sign of one.
MARKS = ["--tA", "--f", "--ink"]


class Palette(unittest.TestCase):
    def check(self, palette, pairs, need):
        return [(a, b, round(contrast(a, b, palette), 2)) for a, b in pairs if contrast(a, b, palette) < need]

    def test_every_text_pair_reads_in_light(self):
        self.assertEqual(self.check(light_vars, TEXT + BADGES["light"], 4.5), [])

    def test_every_text_pair_reads_in_dark(self):
        self.assertEqual(self.check(dark_vars, TEXT + BADGES["dark"], 4.5), [])

    def test_the_marks_stand_out_in_both(self):
        self.assertEqual(self.check(light_vars, [(m, "--bg") for m in MARKS], 3), [])
        self.assertEqual(self.check(dark_vars, [(m, "--bg") for m in MARKS if m != "--f"] + [("--f5", "--bg")], 3), [])

    def test_dark_sets_every_surface(self):
        for name in ("bg", "panel", "soft", "ink", "ink2", "muted", "line", "st", "tip", "tour", "bn"):
            self.assertNotEqual(dark_vars[name], light_vars[name], name)

    def test_the_hand_worked_formula(self):
        self.assertAlmostEqual(contrast("#000000", "#ffffff", {}), 21.0, places=1)
        self.assertAlmostEqual(contrast("#777777", "#ffffff", {}), 4.48, places=2)


if __name__ == "__main__":
    unittest.main()
