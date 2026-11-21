#!/usr/bin/env python3
"""The owner's machine only. Read every board on the page once more and keep the read by its day, so the page can show
what changed from week to week. It never builds, deploys or publishes anything.

    bash owner/weekly.sh                     the exclusion list written again, then one read (a few minutes)
    python3 owner/weekly.py --dry-run        every request it would send, with nothing sent

It reads the boards in data/snapshot/boards.csv through owner/fetch.py's own requests: the same three hosts with
robots.txt read first, the same pauses, retries, size cap and request ceiling, and the same terms gate. The exclusion
list must have been written in the last day, and no company on it is ever requested. A company the list names now also
leaves every earlier read, files and manifest rows alike. Each board goes to
data/raw/weekly/<day>/<provider>_<token>.json.gz (gitignored) beside a manifest.csv of what each one answered, the day
being the run's day in Pacific time, and data/raw/weekly/reads.csv gains a line of counts. A stopped read resumes where
it stopped, and nothing in the output names a company the list holds.
"""
import argparse
import csv
import gzip
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from owner import fetch  # noqa: E402

BOARDS = ROOT.joinpath("data", "snapshot", "boards.csv")
WEEKLY = ROOT.joinpath("data", "raw", "weekly")
LIST_MAX_AGE_HOURS = 24
FIELDS = ["company", "provider", "token", "status", "openings", "bytes", "fetched_at"]
READS = ["day", "boards", "ok", "empty", "gone", "errors", "postings", "left_out", "seconds"]
URL_FOR = dict(fetch.ENDPOINTS)


def today():
    tz = ZoneInfo("America/Los_Angeles") if ZoneInfo else None
    return datetime.now(tz).date().isoformat()


def fresh_list(now=None):
    """The exclusion list, which must have been written in the last day."""
    path = Path(fetch.EXCLUDED)
    if not path.exists():
        raise SystemExit("Stopped: private/exclusions.txt is missing. Run bash owner/weekly.sh, which writes it first.")
    hours = ((now or time.time()) - path.stat().st_mtime) / 3600
    if hours > LIST_MAX_AGE_HOURS:
        raise SystemExit(f"Stopped: private/exclusions.txt was written {hours:.0f} hours ago. Run bash owner/weekly.sh, "
                         "which writes it again first.")
    return fetch.exclusions.load(path)


def boards():
    with open(BOARDS, newline="", encoding="utf-8") as f:
        return [{"company": r["company"], "provider": r["provider"], "token": r["token"]} for r in csv.DictReader(f)]


def read_manifest(folder):
    path = folder.joinpath("manifest.csv")
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {m["company"]: m for m in csv.DictReader(f)}


def write_manifest(folder, rows):
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder.joinpath("manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def purge(ex, root=None):
    """Every earlier read loses each company the list names now. Returns how many boards left, as a count."""
    root, gone = Path(root or WEEKLY), 0
    if not root.exists():
        return 0
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        rows = read_manifest(folder)
        keep = {}
        for company, m in rows.items():
            if ex.matches(company, [m.get("token", "")]):
                f = folder.joinpath(f"{m['provider']}_{m['token']}.json.gz")
                if f.exists():
                    f.unlink()
                gone += 1
                continue
            keep[company] = m
        if len(keep) != len(rows):
            write_manifest(folder, list(keep.values()))
    return gone


def add_reads_line(row, root=None):
    path = Path(root or WEEKLY).joinpath("reads.csv")
    lines = []
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            lines = [r for r in csv.DictReader(f) if r["day"] != row["day"]]
    lines.append(row)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=READS, lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(lines, key=lambda r: r["day"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print the requests it would send and stop")
    a = ap.parse_args(argv)
    providers, notes = fetch.allowed_providers()
    for n in notes:
        print(n)
    ex = fresh_list()
    every = boards()
    rows = [r for r in every if not ex.matches(r["company"], [r["token"]])]
    left_out = len(every) - len(rows)
    if a.dry_run:
        asked = [r for r in rows if r["provider"] in providers]
        for r in asked:
            print(f"{r['company']}: GET {fetch.url_for(URL_FOR[r['provider']], r['token'])}")
        print(f"{len(asked)} requests for {len(asked)} boards, plus one robots.txt for each host. {left_out} boards are "
              f"on the exclusion list and are never requested.")
        return 0
    purged = purge(ex)
    day = today()
    folder = WEEKLY.joinpath(day)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        for note in fetch.load_robots([fetch.HOSTS[p] for p in providers]):
            print(note)
    except fetch.Ceiling:
        print(f"Stopped at the ceiling of {fetch.CEILING} requests before any board was read.")
        return 1
    known = read_manifest(folder)
    started, counts = time.time(), {"ok": 0, "empty": 0, "gone": 0, "errors": 0, "postings": 0}

    def save():
        write_manifest(folder, [known[r["company"]] for r in rows if r["company"] in known])

    try:
        for n, r in enumerate(rows, 1):
            company, provider, token = r["company"], r["provider"], r["token"]
            path = folder.joinpath(f"{provider}_{token}.json.gz")
            m = known.get(company)
            if m and m["status"] in ("ok", "empty", "gone") and (m["status"] != "ok" or path.exists()):
                print(f"[{n}/{len(rows)}] {company}: read already today")
                continue
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            row = {"company": company, "provider": provider, "token": token, "openings": "", "bytes": "",
                   "fetched_at": stamp}
            if provider not in providers:
                known[company] = dict(row, status="skipped")
                print(f"[{n}/{len(rows)}] {company}: {provider} isn't allowed now, so it wasn't read")
                continue
            url = fetch.url_for(URL_FOR[provider], token)
            if not fetch.robots_ok(url):
                known[company] = dict(row, status="robots")
                print(f"[{n}/{len(rows)}] {company}: robots.txt disallows it now")
                continue
            status, body = fetch.get(url)
            jobs = fetch.jobs_in(provider, body) if status == 200 else None
            if jobs:
                path.write_bytes(gzip.compress(body, mtime=0))
                known[company] = dict(row, status="ok", openings=len(jobs), bytes=len(body))
                print(f"[{n}/{len(rows)}] {company}: {len(jobs)} openings")
            elif jobs is not None:
                known[company] = dict(row, status="empty", openings=0)
                print(f"[{n}/{len(rows)}] {company}: the board is empty")
            elif status in (404, 410):
                known[company] = dict(row, status="gone")
                print(f"[{n}/{len(rows)}] {company}: the board is gone ({status})")
            else:
                known[company] = dict(row, status="error")
                print(f"[{n}/{len(rows)}] {company}: answered {status}, so a rerun asks again")
            save()
    except fetch.Ceiling:
        save()
        print(f"Stopped at the ceiling of {fetch.CEILING} requests. Run it again to pick up where it stopped.")
        return 1
    save()
    for m in known.values():
        key = m["status"] if m["status"] in ("ok", "empty", "gone") else "errors"
        counts[key] += 1
        counts["postings"] += int(m["openings"] or 0)
    add_reads_line({"day": day, "boards": len(rows), "left_out": left_out + purged,
                    "seconds": round(time.time() - started), **counts})
    print(f"Done in {round(time.time() - started)} s with {fetch.SENT['n']} requests: {counts['ok']} boards with "
          f"openings, {counts['empty']} empty, {counts['gone']} gone and {counts['errors']} to ask again, holding "
          f"{counts['postings']:,} postings, in data/raw/weekly/{day}/ (gitignored). {left_out + purged} boards were "
          f"left out or taken out for the exclusion list, counted and never named.")
    return 0 if counts["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
