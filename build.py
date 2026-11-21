"""Build the Account Signals page from the snapshot and the recorded briefs.

    python3 build.py               the real page from data/snapshot/, data/out/ranking.json and today's records
    python3 build.py --stand-in    the same with the stand-in's briefs where no model's brief exists yet (never ships)
    python3 build.py --preview     the made-up companies in data/preview/ with the stand-in's briefs (never ships)

It reads every visible word from WORDS.md, writes site/index.html, site/data.js, site/code.js and README.md, checks the fonts are
in place, and stops if the copy lint flags a word or if a word from the never list, another demo's name, a company on
the private exclusion list or a person's details reaches anything that ships. It labels anything frozen that changed
since its freeze and prints the top 15. Standard library only, so it runs anywhere with Python 3.9 or later.
"""
import argparse
import csv
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from app import bundle, code_view, never, page, readme, words  # noqa: E402
from engine import exclusions, privacy  # noqa: E402

SITE = HERE.joinpath("site")
FONTS = ("inter-latin.woff2", "jetbrains-mono-latin.woff2", "Inter-LICENSE.txt", "JetBrainsMono-OFL.txt")
PAGE = ("index.html", "app.css", "data.js", "app.js", "scoring.js", "route.js", "claims.js", "favicon.svg")


def shipped():
    """Every text file that ships and that the scans read."""
    out = [SITE.joinpath(n) for n in PAGE + ("code.js",)]
    out += [HERE.joinpath(n) for n in ("WORDS.md", "README.md", "DATA.md")]
    for folder in ("docs", "data/snapshot"):
        if HERE.joinpath(folder).exists():
            out += sorted(p for p in HERE.joinpath(folder).rglob("*") if p.is_file())
    # The scans read text. The README's screens are images, and Chrome's check looks at what they show.
    return [p for p in out if p.exists() and p.suffix.lower() not in (".png", ".jpg", ".woff2")]


def check_shipped(account_names=()):
    """Every scan on everything that ships: the never list, the other demos' names, the private exclusion list and
    people's details. A missing exclusion list only passes where no raw boards exist (a clean clone)."""
    ex = exclusions.load()
    if not ex.present and HERE.joinpath("data", "raw", "boards").exists():
        return ["private/exclusions.txt is missing on a machine that holds raw boards. Run python3 owner/exclusions.py"]
    paths = shipped()
    names, urls = set(account_names), set()
    snap = HERE.joinpath("data", "snapshot")
    if snap.joinpath("boards.csv").exists():
        with open(snap.joinpath("boards.csv"), newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                names.add(r["company"])
                urls.add(r["board"])
        for n in ("postings.jsonl", "signals.jsonl"):
            for ln in snap.joinpath(n).read_text(encoding="utf-8").splitlines():
                if ln.strip():
                    row = json.loads(ln)
                    url, uid = row.get("url", ""), str(row.get("posting_id", "")).rsplit(":", 1)[-1]
                    urls.add(url)
                    if uid and uid in url:
                        urls.add(url.replace(uid, "{}", 1))  # the page's link patterns, as app/bundle.py writes them
    return never.scan(paths) + exclusions.scan(paths, ex) + privacy.scan(paths, keep=names, allowed_urls=urls)


def lint():
    """The writing rules on every word a reader sees on the page or in the docs, in strict mode. tools/ never ships, so
    a clean clone of the public repo skips this."""
    tool = HERE.joinpath("tools", "lint_copy.py")
    if not tool.exists():
        return []
    spec = importlib.util.spec_from_file_location("lint_copy", str(tool))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    paths = [HERE.joinpath(n) for n in ("WORDS.md", "DATA.md", "README.md")]
    for folder in ("docs", "owner"):
        if HERE.joinpath(folder).exists():
            paths += sorted(HERE.joinpath(folder).glob("*.md"))
    out = []
    for p in (p for p in paths if p.exists()):
        for line in mod.prose(p):
            out += [f"{p.name}: {'; '.join(i)} in \"{s}\"" for s in mod.sentences(line) for i in [mod.check(s, True)] if i]
    return out


def frozen_changes():
    try:
        from evals import freeze
        if not freeze.FROZEN.exists():
            return []
        return [f"{stage}: {path}" for stage, path in freeze.changed()]
    except Exception as e:  # noqa: BLE001 - a clean clone has no freeze record to check
        return [f"the freeze record couldn't be read ({e})"]


def page_weight():
    return sum(SITE.joinpath(n).stat().st_size for n in PAGE if SITE.joinpath(n).exists())


def list_age():
    """Where owner/exclusions.py is here (it never ships): how many of the files the private list is written from
    changed after it was written, or -1 with no list. A clean clone has neither, and gets 0."""
    script = HERE.joinpath("owner", "exclusions.py")
    if not script.exists():
        return 0
    spec = importlib.util.spec_from_file_location("owner_exclusions", str(script))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.stale()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preview", action="store_true", help="the made-up companies with the stand-in's briefs")
    ap.add_argument("--stand-in", action="store_true", help="the stand-in's briefs where no model's brief exists yet")
    ap.add_argument("--quiet", action="store_true", help="only the one-line summary")
    a = ap.parse_args(argv)
    t0 = time.time()
    w = words.load()
    missing = [f for f in FONTS if not SITE.joinpath("fonts", f).exists()]
    if missing:
        sys.exit(f"Stopped: site/fonts/ is missing {', '.join(missing)}.")
    if not a.preview and not HERE.joinpath("data", "out", "ranking.json").exists():
        sys.exit("Stopped: data/out/ranking.json is missing. Run python3 -m engine.rank first.")
    data = bundle.build(preview=a.preview, words=w, stand_in=a.stand_in)
    bundle.write(data)
    code_view.write(w)
    if not a.preview and not data["meta"]["stand_in"]:
        readme.write(data)
    SITE.joinpath("index.html").write_text(page.render(w, data["meta"]["read_on"]), encoding="utf-8")
    SITE.joinpath("favicon.svg").write_text(page.favicon(), encoding="utf-8")
    flagged = lint()
    if flagged:
        sys.exit("Stopped by the copy lint:\n  " + "\n  ".join(flagged))
    problems = check_shipped([x["name"] for x in data["accounts"]])
    if problems:
        sys.exit("Stopped: " + "; ".join(problems))
    briefs = data["briefs"]
    read = sum(1 for bs in briefs.values() for b in bs if b["read"])
    kind = "preview" if a.preview else "dry build with the stand-in" if data["meta"]["stand_in"] else "page"
    print(f"Built the {kind} in {time.time() - t0:.2f} s: {len(data['accounts'])} accounts, "
          f"{sum(len(bs) for bs in briefs.values())} briefs for {len(briefs)} accounts ({read} with the second read), "
          f"{page_weight() / 1024:.0f} KB before the fonts and the code view.")
    age = 0 if a.preview else list_age()
    if age:
        print("Note: " + ("there's no private exclusion list. " if age < 0 else
                          f"{age} of the files the private exclusion list comes from changed after it was written. ") +
              "Run python3 owner/exclusions.py and build again before anything goes out.")
    if a.quiet:
        return 0
    for line in frozen_changes():
        print(f"  Changed since its freeze: {line}")
    if not a.preview and not briefs:
        print("  No scored brief yet matches today's prompt, so the page shows the accounts without briefs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
