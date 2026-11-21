#!/usr/bin/env python3
"""The owner's machine only, about a minute. Ask each model in config/models.json for one word through claude -p, the
way the recorder will, and print what came back: the model the command line answered with, the seconds, and the
command line's own reason when a call fails. Run it before the first real run, or after a run stops on a model.

    python3 owner/claude_check.py           (from the build folder)

It sends no project text, only a one-line question, and it records nothing.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from agents import llm  # noqa: E402


def main():
    cfg = json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))
    used = list(dict.fromkeys(cfg["compare"] + cfg["judges"]))
    entries = {m["id"]: m for m in cfg["models"]}
    bad = 0
    for mid in used:
        e = entries[mid]
        try:
            text, meta = llm.backend_for(e, lambda item: None)("Reply with the word OK and nothing else.", "a quick check")
            print(f"  {e['label']:18} asked as {e['model']}: answered by {', '.join(meta.get('models') or []) or '?'} "
                  f"in {round((meta.get('ms') or 0) / 1000, 1)} s, saying {text.strip()[:20]!r}")
        except Exception as err:  # noqa: BLE001 - every model gets its own line
            bad += 1
            print(f"  {e['label']:18} asked as {e['model']}: FAILED, {err}")
    print("Every model answered." if not bad else f"{bad} of {len(used)} failed. Paste this to the career session.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
