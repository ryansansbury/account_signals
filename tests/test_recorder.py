"""The recorder offline, with the stand-in and fake models: a clean pass, a repair after malformed JSON, a brief that
still fails after its one repair, the splits, and a full stand-in run that skips what it already recorded."""
import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from agents import inputs
from engine import signals as sigmod

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("owner_record", HERE.joinpath("owner", "record_briefs.py"))
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)
from owner import stand_in  # noqa: E402

LABELS = {k: sigmod.as_label(v["label"]) for k, v in sigmod.load_config()["families"].items()}
SIGS = [
    {"sid": "s1", "account": "Wobbleton Freight", "family": "revops", "tool": "", "title": "Revenue Operations Manager",
     "excerpt": "Revenue Operations Manager", "posted": "2026-11-05", "date_kind": "published", "posting_id": "g:w:101",
     "strength": "", "temporary": False, "read_on": "2026-11-09"},
    {"sid": "s4", "account": "Wobbleton Freight", "family": "crm_move", "tool": "", "title": "Revenue Operations Manager",
     "excerpt": "You'll lead our move off spreadsheets to a single CRM this quarter and build the forecast our sales "
                "leaders use every week.", "posted": "2026-11-05", "date_kind": "published", "posting_id": "g:w:101",
     "strength": "", "temporary": False, "read_on": "2026-11-09"},
]
ACCOUNT = {"account": "Wobbleton Freight", "read_on": "2026-11-09", "openings": 48, "us": 44, "nonus": 4,
           "hub": {"city": "Denver", "state": "CO"},
           "intent_rows": [{"sid": "s4", "family": "crm_move", "points": 31.9}, {"sid": "s1", "family": "revops",
                                                                                 "points": 36.5}]}


def fake(*replies):
    calls = []

    def model(system, user):
        calls.append(user)
        r = replies[min(len(calls) - 1, len(replies) - 1)]
        text = r(system, user)[0] if callable(r) else r
        return text, {"ms": 5, "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.001, "model": "fake"}
    model.calls = calls
    return model


class Recorder(unittest.TestCase):
    def setUp(self):
        self.chosen = inputs.pick(ACCOUNT, SIGS)
        self.lint = rb.lint_function()

    def record(self, model):
        return rb.record_one(ACCOUNT, self.chosen, LABELS, model, "fake", "Fake", "dev", rb.claims.load_tools(),
                             self.lint, now="2026-11-09T20:00:00+00:00")

    def test_the_message_holds_only_the_sources(self):
        user, sources = inputs.message(ACCOUNT, self.chosen, LABELS)
        self.assertIn("[0] Board. Wobbleton Freight had 48 open roles on its public job board on 2026-11-09. The US city "
                      "with the most of its open roles was Denver, CO. The US held 92% of the roles that named a place.",
                      user)
        self.assertIn('[1] Posting "Revenue Operations Manager", published 2026-11-05. Signal: revenue operations role',
                      user)
        self.assertIn('[2] Posting "Revenue Operations Manager", published 2026-11-05 (same posting as [1]). Signal:',
                      user)
        self.assertIn('Quote: "You\'ll lead our move off spreadsheets', user)
        self.assertEqual(sorted(sources), [0, 1, 2])

    def test_a_pace_signal_never_repeats_a_posting(self):
        pace = [dict(SIGS[0], sid="p1", family="pace", excerpt=SIGS[0]["title"]),
                dict(SIGS[0], sid="p2", family="pace", title="Account Executive", excerpt="Account Executive",
                     posting_id="g:w:105")]
        acct = dict(ACCOUNT, intent_rows=ACCOUNT["intent_rows"] + [{"sid": "p1", "family": "pace", "points": 5},
                                                                   {"sid": "p2", "family": "pace", "points": 5}])
        self.assertEqual([s["sid"] for s in inputs.pick(acct, SIGS + pace)], ["s1", "s4", "p2"])

    def test_the_writing_check_keeps_a_city_and_its_state_together(self):
        if self.lint is None:
            self.skipTest("the copy lint isn't in this folder")
        self.assertEqual(self.lint("Most of its open roles were in Lehi, UT and the rest were remote."), [])
        self.assertTrue(self.lint("The board lists two roles, most of them in Lehi."))

    def test_the_stand_in_passes_every_check_on_its_first_try(self):
        rec = self.record(stand_in.model)
        self.assertEqual(len(rec["attempts"]), 1)
        self.assertFalse(rec["final"]["needs_review"], rec["final"]["check"])

    def test_malformed_json_gets_one_repair(self):
        model = fake("Sure, here it is, but no JSON.", stand_in.model)
        rec = self.record(model)
        self.assertEqual(len(rec["attempts"]), 2)
        self.assertTrue(rec["final"]["repaired"])
        self.assertFalse(rec["final"]["needs_review"])
        self.assertIn("It had these problems", model.calls[1])

    def test_a_reply_cut_off_at_the_limit_says_so(self):
        good = stand_in.model("", inputs.message(ACCOUNT, self.chosen, LABELS)[0])[0]
        calls = []

        def model(system, user):
            calls.append(user)
            if len(calls) == 1:
                return good[:200], {"ms": 5, "output_tokens": 16000, "cost_usd": 0.001, "stop_reason": "max_tokens"}
            return good, {"ms": 5, "output_tokens": 900, "cost_usd": 0.001, "stop_reason": "end_turn"}
        rec = self.record(model)
        self.assertTrue(rec["attempts"][0]["shape_errors"][0].startswith("the reply was cut off"))
        self.assertIn("the reply was cut off", calls[1])
        self.assertFalse(rec["final"]["needs_review"])

    def test_a_brief_that_still_fails_is_kept_and_needs_review(self):
        good = json.loads(stand_in.model("", inputs.message(ACCOUNT, self.chosen, LABELS)[0])[0])
        good["why_now"][0]["text"] = "Their CRO, Jordan Blake, posted the Revenue Operations Manager role [1]."
        model = fake(json.dumps(good))
        rec = self.record(model)
        self.assertEqual(len(rec["attempts"]), 2)
        self.assertTrue(rec["final"]["needs_review"])
        self.assertIn("name: Jordan", rec["attempts"][0]["check"]["sentences"][0]["problems"])
        self.assertEqual(rec["cost_usd"], 0.002)

    def test_the_splits(self):
        ranking = [dict(ACCOUNT, account=f"Made Up {i:02d}") for i in range(1, 46)]
        ranking[2]["intent_rows"] = [{"sid": "p1", "family": "pace", "points": 1}]
        top = rb.pick_accounts(ranking, "briefs")
        self.assertEqual(len(top), 25)
        self.assertNotIn("Made Up 03", [a["account"] for a in top])
        dev = rb.pick_accounts(ranking, "dev")
        self.assertEqual([a["account"] for a in dev], [f"Made Up {i}" for i in range(27, 33)])
        self.assertFalse({a["account"] for a in dev} & {a["account"] for a in top})

    def test_an_account_tuned_on_stays_dev_when_it_climbs(self):
        ranking = [dict(ACCOUNT, account=f"Made Up {i:02d}") for i in range(1, 46)]
        pinned = ("Made Up 10", "Made Up 28", "Made Up 30", "Made Up 44")
        top = [a["account"] for a in rb.pick_accounts(ranking, "briefs", pinned)]
        dev = [a["account"] for a in rb.pick_accounts(ranking, "dev", pinned)]
        self.assertEqual(len(top), 25)
        self.assertNotIn("Made Up 10", top)
        self.assertIn("Made Up 26", top)
        self.assertEqual(dev, ["Made Up 10", "Made Up 27", "Made Up 28", "Made Up 29", "Made Up 30", "Made Up 44"])
        self.assertFalse(set(dev) & set(top))


class StandInRun(unittest.TestCase):
    def test_a_stand_in_run_records_and_then_skips(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(dir=scratch))
        try:
            ranking = tmp.joinpath("ranking.json")
            ranking.write_text(json.dumps({"accounts": [dict(ACCOUNT, account=f"Made Up {i:02d}") for i in range(1, 30)]}),
                               encoding="utf-8")
            sigs = tmp.joinpath("signals.jsonl")
            sigs.write_text("".join(json.dumps(dict(s, account=f"Made Up {i:02d}")) + "\n"
                                    for i in range(1, 30) for s in SIGS), encoding="utf-8")
            saved = (rb.RANKING, rb.SIGNALS)
            rb.RANKING, rb.SIGNALS = ranking, sigs
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(rb.main(["--split", "dev", "--stand-in"], runs=tmp.joinpath("runs")), 0)
                self.assertEqual(rb.main(["--split", "dev", "--stand-in"], runs=tmp.joinpath("runs")), 0)
            rb.RANKING, rb.SIGNALS = saved
            recs = sorted(tmp.joinpath("runs", "brief").rglob("stand-in.json"))
            self.assertEqual(len(recs), 4)
            self.assertEqual(out.getvalue().count("recorded already"), 4)
            self.assertEqual(len(tmp.joinpath("runs", "audit.jsonl").read_text(encoding="utf-8").splitlines()), 4)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
