#!/usr/bin/env python3
"""The owner's machine only. Match each account on the page to an SEC identity and keep what its filings say.

    python3 owner/sec.py               the read and the match (a few minutes the first time)
    python3 owner/sec.py --dry-run     what it would ask for, with nothing sent

It reads only www.sec.gov and data.sec.gov, and only these: company_tickers.json, the Form D data sets page and its
quarterly files from 2024 on, and the submissions file of each matched company, plus the financial facts of each
matched company with a ticker. It never asks for anything under /cgi-bin, it reads each host's robots.txt first and
skips whatever that disallows, and it asks at most twice a second. The SEC asks for ten a second at most, and a run it
throttles stops at once and says to wait ten minutes. Every request carries a User-Agent that names the project and the
person and address in private/sec_contact.txt, which is written once from git's own name and email when it's missing
and never ships or prints.

Each Form D data set is read in memory, and only its filing, issuer and offering tables are opened. The tables that
name people are never read or saved. Everything goes to data/raw/sec/ (gitignored): the tickers, each quarter's Form D
rows, each matched company's submissions and facts, data/raw/sec/identities.json and data/raw/sec/form_d.json, which
the forward test reads. config/sec_identities.csv takes the matches with their evidence and no names of people. A
stopped run resumes where it stopped. config/sources.json must allow the SEC from a terms check in the last 45 days.
"""
import argparse
import csv
import io
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import exclusions, sec  # noqa: E402

SOURCES = ROOT.joinpath("config", "sources.json")
CONTACT = ROOT.joinpath("private", "sec_contact.txt")
RANKING = ROOT.joinpath("data", "out", "ranking.json")
DOMAINS = ROOT.joinpath("config", "domains.csv")
OUT = ROOT.joinpath("data", "raw", "sec")
CSV_OUT = ROOT.joinpath("config", "sec_identities.csv")
TICKERS = "https://www.sec.gov/files/company_tickers.json"
FORM_D_PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ALLOWED = {"www.sec.gov": ("/files/company_tickers.json", "/data-research/sec-markets-data/form-d-data-sets",
                           "/robots.txt"),
           "data.sec.gov": ("/submissions/CIK", "/api/xbrl/companyfacts/CIK", "/robots.txt")}
# A quarterly Form D data set wherever the SEC files it under /files/ (it moved folders in 2026), and nothing else.
FORM_D_FILE = re.compile(r"^/files/[a-z0-9_-]+/data/form-d-data-sets/\d{4}q[1-4]_d\.zip$", re.I)
FIRST_QUARTER = "2024q1"
DELAY = 0.5
TIMEOUT = 60
MAX_BYTES = 80 * 1024 * 1024
FIELDS = ["company", "cik", "source", "ticker", "confidence", "evidence"]
LAST, ROBOTS, SENT = {"t": 0.0}, {}, {"n": 0}


class Throttled(Exception):
    pass


def allowed(sources_path=None, today=None):
    cfg = json.loads(Path(sources_path or SOURCES).read_text(encoding="utf-8"))
    s = cfg["sources"].get("sec") or {}
    if not s.get("allowed"):
        raise SystemExit("Stopped: config/sources.json doesn't allow the SEC.")
    age = ((today or date.today()) - date.fromisoformat(s["checked"])).days
    if age > cfg.get("max_age_days", 45):
        raise SystemExit(f"Stopped: the SEC's terms were checked {age} days ago. Run the terms prompt again first.")
    return s


def contact(path=None, runner=subprocess.run):
    """The person and address the User-Agent names, from private/sec_contact.txt, written once from git's config."""
    path = Path(path or CONTACT)
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
    else:
        get = lambda key: runner(["git", "config", key], capture_output=True, text=True).stdout.strip()  # noqa: E731
        name, email = get("user.name"), get("user.email")
        if not name or "@" not in email:
            raise SystemExit("Stopped: put your name and email on one line in private/sec_contact.txt, as the SEC "
                             "asks every request to carry them.")
        text = f"{name} {email}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print("Wrote private/sec_contact.txt from git's name and email. It never ships.")
    if "@" not in text:
        raise SystemExit("Stopped: private/sec_contact.txt needs a name and an email on one line.")
    return text


def check_url(url):
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.hostname not in ALLOWED or "/cgi-bin" in u.path:
        raise ValueError(f"refusing a URL off the allowlist: {url}")
    if not u.path.startswith(ALLOWED[u.hostname]) and not (u.hostname == "www.sec.gov" and FORM_D_FILE.match(u.path)):
        raise ValueError(f"refusing a path off the allowlist: {url}")


def get(url, ua):
    """(status, body). A throttle (403 or 429) raises, since the SEC asks for ten quiet minutes before anything else."""
    check_url(url)
    wait = LAST["t"] + DELAY - time.time()
    if wait > 0:
        time.sleep(wait)
    LAST["t"] = time.time()
    SENT["n"] += 1
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(MAX_BYTES + 1)
            return (413, b"") if len(body) > MAX_BYTES else (r.status, body)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise Throttled()
        return e.code, b""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, str(e).encode()


def load_robots(ua, fetch=None):
    fetch = fetch or (lambda u: get(u, ua))
    for host in ALLOWED:
        status, body = fetch(f"https://{host}/robots.txt")
        if status == 200:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(body.decode("utf-8", "replace").splitlines())
            ROBOTS[host] = rp
        else:
            ROBOTS[host] = None if status in (404, 410) else False


def robots_ok(url, ua):
    rp = ROBOTS.get(urllib.parse.urlparse(url).hostname)
    return False if rp is False else True if rp is None else rp.can_fetch(ua, url)


def quarters(page):
    """{"2026q3": url} for every Form D data set the page links, from the first quarter on."""
    out = {}
    for href in re.findall(r"""href=["']([^"']+\.zip)["']""", page, re.I):
        m = re.search(r"(\d{4})\s*q([1-4])", href, re.I)
        if m and "form-d" in href.lower():
            q = f"{m.group(1)}q{m.group(2)}"
            if q >= FIRST_QUARTER:
                out[q] = urllib.parse.urljoin(FORM_D_PAGE, href)
    return dict(sorted(out.items()))


def domains():
    if not DOMAINS.exists():
        return {}
    with open(DOMAINS, newline="", encoding="utf-8") as f:
        return {r["company"]: r["domain"] for r in csv.DictReader(line for line in f if not line.startswith("#"))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print what it would ask for and stop")
    ap.add_argument("--offline", action="store_true", help="match again from what's saved, with nothing sent")
    a = ap.parse_args(argv)
    allowed()
    accounts = json.loads(RANKING.read_text(encoding="utf-8"))["accounts"]
    ex = exclusions.load()
    accounts = [x for x in accounts if not ex.matches(x["account"])]
    if a.dry_run:
        print(f"It would read robots.txt on two hosts, {TICKERS}, {FORM_D_PAGE} and each quarterly Form D file it "
              f"links from {FIRST_QUARTER} on, then one submissions file for each of the {len(accounts)} accounts that "
              f"matches and the financial facts of each that has a ticker, at most twice a second.")
        return 0
    ua = "" if a.offline else f"AccountSignals/1.0 {contact()}"
    started = time.time()
    if a.offline:
        ROBOTS.update({h: False for h in ALLOWED})  # every URL reads as off, so nothing is sent
    try:
        if not a.offline:
            load_robots(ua)
        for d in ("formd", "submissions", "facts"):
            OUT.joinpath(d).mkdir(parents=True, exist_ok=True)
        tick_path = OUT.joinpath("company_tickers.json")
        if not tick_path.exists():
            if not robots_ok(TICKERS, ua):
                raise SystemExit("Stopped: robots.txt disallows the tickers file now.")
            status, body = get(TICKERS, ua)
            if status != 200:
                raise SystemExit(f"Stopped: the tickers file answered {status}.")
            tick_path.write_bytes(body)
        ticker_rows = sec.tickers(tick_path.read_bytes())
        status, page = get(FORM_D_PAGE, ua) if robots_ok(FORM_D_PAGE, ua) else (0, b"")
        links = quarters(page.decode("utf-8", "replace")) if status == 200 else {}
        if not links and not a.offline:
            print("No Form D data sets were linked on the SEC's page, so companies without a ticker can't be matched "
                  "this run.")
        for q, url in links.items():
            path = OUT.joinpath("formd", f"{q}.json")
            if path.exists() or not robots_ok(url, ua):
                continue
            try:
                status, body = get(url, ua)
            except ValueError:
                print(f"{q}: the SEC links this data set at an address this script doesn't read, so it was skipped")
                continue
            if status != 200:
                print(f"{q}: the data set answered {status}, so a rerun asks again")
                continue
            rows = sec.form_d_rows(zipfile.ZipFile(io.BytesIO(body)))
            path.write_text(json.dumps(rows) + "\n", encoding="utf-8")
            print(f"{q}: {len(rows):,} Form D filings read, and the tables that name people were never opened")
        form_d_all = [r for p in sorted(OUT.joinpath("formd").glob("*.json"))
                      for r in json.loads(p.read_text(encoding="utf-8"))]
        sites, ids, filed, by = domains(), {}, {}, sec.index(ticker_rows, form_d_all)
        for acct in sorted(accounts, key=lambda x: x["account"]):
            m = sec.match(acct, ticker_rows, form_d_all, by)
            if m["cik"]:
                sub_path = OUT.joinpath("submissions", f"CIK{m['cik']:010d}.json")
                url = SUBMISSIONS.format(cik=m["cik"])
                if not sub_path.exists() and robots_ok(url, ua):
                    status, body = get(url, ua)
                    if status == 200:
                        sub_path.write_bytes(body)
                if sub_path.exists():
                    subs = json.loads(sub_path.read_text(encoding="utf-8"))
                    m = sec.confirm(m, subs, acct, sites.get(acct["account"], ""))
                    dates = {d for d, _, _ in sec.form_d_dates(subs)}
                    dates |= {r["filed"] for r in form_d_all if r["cik"] == m["cik"] and r["filed"]}
                    filed[acct["account"]] = sorted(dates)
                if m["source"] == "ticker":
                    facts_path = OUT.joinpath("facts", f"CIK{m['cik']:010d}.json")
                    url = FACTS.format(cik=m["cik"])
                    if not facts_path.exists() and robots_ok(url, ua):
                        status, body = get(url, ua)
                        if status == 200:
                            facts_path.write_bytes(body)
            ids[acct["account"]] = m
    except Throttled:
        print("Stopped: the SEC throttled this run. Wait at least ten minutes, then run it again. It picks up where it "
              "stopped.")
        return 1
    OUT.joinpath("identities.json").write_text(json.dumps(ids, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    OUT.joinpath("form_d.json").write_text(json.dumps(filed, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
        f.write("# Each account's SEC identity (owner/sec.py) with the evidence behind it. No person's name.\n")
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for name in sorted(ids):
            m = ids[name]
            w.writerow({"company": name, "cik": m["cik"] or "", "source": m.get("source", ""),
                        "ticker": m.get("ticker", ""), "confidence": m["confidence"],
                        "evidence": " and ".join(m["evidence"])})
    tally = {}
    for m in ids.values():
        key = m["confidence"] if not m["cik"] else f"{m['source']} {m['confidence']}"
        tally[key] = tally.get(key, 0) + 1
    print(f"Done in {round(time.time() - started)} s with {SENT['n']} requests. "
          f"{sum(1 for m in ids.values() if m['cik'])} of {len(ids)} accounts matched an SEC identity "
          f"({', '.join(f'{v} {k}' for k, v in sorted(tally.items()))}), and {sum(1 for v in filed.values() if v)} "
          f"have a Form D on file. Wrote data/raw/sec/ (gitignored) and config/sec_identities.csv.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
