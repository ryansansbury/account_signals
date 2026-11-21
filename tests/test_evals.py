"""Replay, the scoreboard and the freeze, on records the recorder makes offline."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from agents import replay
from evals import freeze, score
from tests import test_recorder as tr

HERE = Path(__file__).resolve().parent.parent


class Evals(unittest.TestCase):
    def setUp(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(dir=scratch))
        rec = tr.Recorder("test_the_splits")
        rec.setUp()
        runs = self.tmp.joinpath("runs", "brief", "wobbleton-freight")
        runs.mkdir(parents=True)
        good = rec.record(tr.stand_in.model)
        good["model"], good["split"] = "model-a", "dev"
        bad_brief = json.loads(tr.stand_in.model("", tr.inputs.message(tr.ACCOUNT, rec.chosen, tr.LABELS)[0])[0])
        bad_brief["why_now"][0]["text"] = "They posted 9 roles [1]."
        bad = rec.record(tr.fake(json.dumps(bad_brief)))
        bad["model"], bad["split"] = "model-b", "dev"
        runs.joinpath("model-a.json").write_text(json.dumps(good), encoding="utf-8")
        runs.joinpath("model-b.json").write_text(json.dumps(bad), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_replay_rechecks_and_the_scoreboard_picks_the_route(self):
        recs = replay.load_all(self.tmp.joinpath("runs"))
        self.assertEqual(len(recs), 2)
        for r in recs:
            fresh, differs = replay.recheck(r, tools=None, lint=None)
            self.assertFalse(differs and r["model"] == "model-a" and fresh["ok"] != r["final"]["check"]["ok"])
        result = score.score(recs)
        a, b = result["splits"]["dev"]["model-a"], result["splits"]["dev"]["model-b"]
        self.assertEqual((a["first_passed"], a["needs_review"], a["clears_bars"]), (1, 0, True))
        self.assertEqual((b["needs_review"], b["first_unsupported"], b["clears_bars"]), (1, 1, False))
        self.assertEqual(result["route"], "model-a")

    def test_a_stale_prompt_is_refused(self):
        p = self.tmp.joinpath("runs", "brief", "wobbleton-freight", "model-a.json")
        rec = json.loads(p.read_text(encoding="utf-8"))
        rec["prompt_hash"] = "0" * 16
        p.write_text(json.dumps(rec), encoding="utf-8")
        with self.assertRaises(replay.Stale):
            replay.load_all(self.tmp.joinpath("runs"))
        self.assertEqual(len(replay.load_all(self.tmp.joinpath("runs"), strict=False)), 2)

    def test_the_freeze_records_and_catches_a_change(self):
        root = self.tmp.joinpath("root")
        root.joinpath("prompts").mkdir(parents=True)
        root.joinpath("prompts", "brief.md").write_text("v1", encoding="utf-8")
        path = self.tmp.joinpath("frozen.json")
        freeze.freeze("prompt", path=path, root=root)
        self.assertEqual(freeze.changed(path, root), [])
        with self.assertRaises(SystemExit):
            freeze.freeze("prompt", path=path, root=root)
        root.joinpath("prompts", "brief.md").write_text("v2", encoding="utf-8")
        self.assertEqual(freeze.changed(path, root), [("prompt", "prompts/brief.md")])
        freeze.freeze("prompt", again=True, path=path, root=root)
        self.assertEqual(len(json.loads(path.read_text(encoding="utf-8"))["history"]), 1)


if __name__ == "__main__":
    unittest.main()
