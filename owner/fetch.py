#!/usr/bin/env python3
"""The owner's machine only. Read each seed company's public job board once and save it for the build.

    bash owner/fetch.sh                      the full run, about 15 minutes
    python3 owner/fetch.py --dry-run         every request it would send and the total, with nothing sent
    python3 owner/fetch.py --refresh         read every board again, for a refresh

It reads the public, unauthenticated job board APIs that Greenhouse, Lever and Ashby publish so companies can show their
openings on their own sites. It sends GET requests only, over HTTPS with certificate checks, to those three hosts only,
and it refuses a redirect to any other host. It pauses between requests, retries once after a rate limit, a server
error or a network error, skips any response over 25 MB, and stops at 3,500 requests. It sends no cookies, keys or
personal data, and its User-Agent names the project and its public repo.

Two gates come first. A provider is read only when config/providers.json marks it allowed from a terms check made in
the last 45 days (DATA.md records the terms), and the run stops when private/exclusions.txt is missing or more than
seven days old. No company on that list is ever requested, and a board whose own name is on it is deleted as soon as
it's read. Neither shows up in the output except as a count.

Boards go to data/raw/boards/ (gitignored). The manifest, data/raw/manifest.csv, keeps a row for every company asked
about and is rewritten after each one, so a stopped run resumes and a rerun asks only about what's unsettled. An empty
board doesn't end the search, since a company that moved providers can leave an empty board behind.
"""
import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import exclusions  # noqa: E402

SEED = ROOT.joinpath("config", "accounts.csv")
RAW = ROOT.joinpath("data", "raw")
PROVIDERS = ROOT.joinpath("config", "providers.json")
EXCLUDED = ROOT.joinpath("private", "exclusions.txt")
UA = "AccountSignals/1.0 (+https://github.com/ryansansbury/account_signals; public job board API, one read per board)"
ENDPOINTS = (
    ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true"),
    ("ashby", "https://api.ashbyhq.com/posting-api/job-board/{t}?includeCompensation=false"),
    ("lever", "https://api.lever.co/v0/postings/{t}?mode=json"),
)
GREENHOUSE_BOARD = "https://boards-api.greenhouse.io/v1/boards/{t}"
HOSTS = {"greenhouse": "boards-api.greenhouse.io", "ashby": "api.ashbyhq.com", "lever": "api.lever.co"}
ALLOWED_HOSTS = set(HOSTS.values())
# Only the public job board paths (and robots.txt) on each host, so nothing such as Greenhouse's /embed/ is ever asked.
ALLOWED_PATHS = {"boards-api.greenhouse.io": "/v1/boards/", "api.ashbyhq.com": "/posting-api/job-board/",
                 "api.lever.co": "/v0/postings/"}
TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,59}$")
MAX_BYTES = 25 * 1024 * 1024
DELAY = 0.4
HOST_DELAY = {"api.lever.co": 1.1}  # Lever's robots.txt is reported to ask for a one-second crawl delay (DATA.md)
RETRY_WAITS = (5, 30)
TIMEOUT = 30
CEILING = 3500
LIST_MAX_AGE_DAYS = 7
FIELDS = ["company", "status", "provider", "token", "openings", "url", "fetched_at", "board_name", "bytes", "tried"]


class Ceiling(Exception):
    pass


class SameHosts(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only when it stays on HTTPS and on one of the three API hosts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlparse(newurl)
        if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(SameHosts())
SENT = {"n": 0}
LAST, ROBOTS = {}, {}


def check_url(url):
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"refusing a URL off the allowlist: {url}")
    if u.path != "/robots.txt" and not u.path.startswith(ALLOWED_PATHS[u.hostname]):
        raise ValueError(f"refusing a path off the allowlist: {url}")


def pace(host):
    """Wait out the host's delay since its last request: the base delay, Lever's one second, or more if robots.txt
    asks for more."""
    rp = ROBOTS.get(host)
    asked = (rp.crawl_delay(UA) if rp else None) or 0
    wait = LAST.get(host, 0.0) + max(DELAY, HOST_DELAY.get(host, 0), float(asked)) - time.time()
    if wait > 0:
        time.sleep(wait)
    LAST[host] = time.time()


def get(url):
    """(status, body). A rate limit is retried after 5 and then 30 seconds, a server or network error once after 5.
    413 for an oversized body."""
    check_url(url)
    host = urllib.parse.urlparse(url).hostname
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}, method="GET")
    for attempt in (1, 2, 3):
        if SENT["n"] >= CEILING:
            raise Ceiling()
        pace(host)
        SENT["n"] += 1
        try:
            with OPENER.open(req, timeout=TIMEOUT) as r:
                body = r.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    return 413, b""
                return r.status, body
        except urllib.error.HTTPError as e:
            if (e.code == 429 and attempt < 3) or (e.code in (500, 502, 503, 504) and attempt < 2):
                time.sleep(RETRY_WAITS[attempt - 1])
                continue
            return e.code, b""
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < 2:
                time.sleep(RETRY_WAITS[0])
                continue
            return 0, str(e).encode()
    return 0, b""


def load_robots(hosts):
    """Read each host's robots.txt once at the start of a run. A missing file disallows nothing. Any other failure keeps
    that host off for the run, the cautious reading."""
    notes = []
    for host in hosts:
        status, body = get(f"https://{host}/robots.txt")
        if status == 200:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(body.decode("utf-8", "replace").splitlines())
            ROBOTS[host] = rp
            delay = rp.crawl_delay(UA)
            notes.append(f"{host}: robots.txt read" + (f", crawl delay {delay} s" if delay else ""))
        elif status in (404, 410):
            ROBOTS[host] = None
            notes.append(f"{host}: no robots.txt, so nothing is disallowed")
        else:
            ROBOTS[host] = False
            notes.append(f"{host}: robots.txt answered {status}, so this host stays off for this run")
    return notes


def robots_ok(url):
    rp = ROBOTS.get(urllib.parse.urlparse(url).hostname)
    if rp is False:
        return False
    return True if rp is None else rp.can_fetch(UA, url)


def allowed_providers(path=None, today=None):
    """([provider names the terms allow], [a note for each one they don't])."""
    cfg = json.loads(Path(path or PROVIDERS).read_text(encoding="utf-8"))
    today = today or date.today()
    out, notes = [], []
    for name, p in cfg["providers"].items():
        if not p.get("allowed"):
            notes.append(f"{name} is off: {p.get('status') or 'not allowed by config/providers.json'}")
            continue
        try:
            age = (today - date.fromisoformat(p.get("checked") or "")).days
        except ValueError:
            notes.append(f"{name} is off: its terms check has no date")
            continue
        if age > cfg.get("max_age_days", 45):
            notes.append(f"{name} is off: its terms were checked {age} days ago, so run the terms prompt again")
            continue
        out.append(name)
    return out, notes


def exclusion_list(path=None, now=None):
    path = Path(path or EXCLUDED)
    if not path.exists():
        raise SystemExit("Stopped: private/exclusions.txt is missing. Run python3 owner/exclusions.py first.")
    age = ((now or time.time()) - path.stat().st_mtime) / 86400
    if age > LIST_MAX_AGE_DAYS:
        raise SystemExit(f"Stopped: private/exclusions.txt is {age:.0f} days old. Run python3 owner/exclusions.py again.")
    return exclusions.load(path)


def candidates(row):
    """The seed's own tokens first, then two made from the name, three at most."""
    out = [t.strip() for t in (row.get("tokens") or "").split(";") if t.strip()]
    name = exclusions.full(row["company"])
    for t in (re.sub(r"[^a-z0-9]", "", name), re.sub(r"[^a-z0-9]+", "-", name).strip("-")):
        if t and t not in out:
            out.append(t)
    return [t for t in out if TOKEN.match(t)][:3]


def url_for(pattern, token):
    return pattern.format(t=urllib.parse.quote(token, safe=""))


def jobs_in(provider, body):
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if provider == "lever":
        return data if isinstance(data, list) else None
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return data["jobs"]
    return None


def board_names(provider, token, body):
    """The names a board gives for itself: Greenhouse's board name (one more request) and any company name on a job."""
    names = set()
    jobs = jobs_in(provider, body) or []
    for j in jobs[:200]:
        if isinstance(j, dict) and j.get("company_name"):
            names.add(str(j["company_name"]))
    meta_url = url_for(GREENHOUSE_BOARD, token)
    if provider == "greenhouse" and robots_ok(meta_url):
        status, meta = get(meta_url)
        if status == 200:
            try:
                names.add(json.loads(meta).get("name", "") or "")
            except ValueError:
                pass
    return {n for n in names if n}


def settled(m, row, boards, providers):
    """True when the last run settled a company: a saved board with openings, or a search of every allowed provider and
    token that ended without a network error."""
    if m["status"] == "dropped":
        return True
    saved = boards.joinpath(f"{m['provider']}_{m['token']}.json").exists() if m["status"] == "ok" else True
    if m["status"] == "ok" and m["openings"] not in ("", "0"):
        return saved
    tried = (m.get("tried") or "").split()
    asked = {t.rsplit(":", 1)[0] for t in tried}
    every = {f"{p}:{t}" for p in providers for t in candidates(row)}
    return saved and every <= asked and all(t.rsplit(":", 1)[-1] != "0" for t in tried)


def write_manifest(rows):
    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW.joinpath("manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def read_manifest():
    path = RAW.joinpath("manifest.csv")
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {m["company"]: m for m in csv.DictReader(f)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print the requests it would send and stop")
    ap.add_argument("--refresh", action="store_true", help="read every board again")
    a = ap.parse_args(argv)
    providers, notes = allowed_providers()
    for n in notes:
        print(n)
    if not providers:
        print("Stopped: no provider is allowed yet. The terms check fills in config/providers.json.")
        return 1
    ex = exclusion_list()
    with open(SEED, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows, left_out = ex.keep(rows)
    endpoints = [(p, pattern) for p, pattern in ENDPOINTS if p in providers]
    if a.dry_run:
        n = 0
        for row in rows:
            for provider, pattern in endpoints:
                for token in candidates(row):
                    print(f"{row['company']}: GET {url_for(pattern, token)}")
                    n += 1
        print(f"At most {n} requests for {len(rows)} companies on {', '.join(providers)}, plus one board-name request "
              f"for each Greenhouse board found. It stops trying a company at its first board with openings. "
              f"{left_out} seed companies are on the exclusion list and are never requested. The real run reads each "
              f"host's robots.txt first and skips anything it disallows, and asks Lever at most once a second.")
        return 0
    try:
        for note in load_robots([HOSTS[p] for p in providers]):
            print(note)
    except Ceiling:
        print(f"Stopped at the ceiling of {CEILING} requests before any board was read.")
        return 1
    boards = RAW.joinpath("boards")
    boards.mkdir(parents=True, exist_ok=True)
    known = {} if a.refresh else read_manifest()
    purged = 0
    for company in list(known):
        m = known[company]
        if ex.matches(company, [m.get("token", "")]):
            board = boards.joinpath(f"{m['provider']}_{m['token']}.json")
            if m.get("provider") and board.exists():
                board.unlink()
            del known[company]
            purged += 1
    order = [row["company"] for row in rows]

    def save():
        write_manifest([{k: known[c].get(k, "") for k in FIELDS} for c in order if c in known])

    total_bytes, started, dropped = 0, time.time(), 0
    try:
        for n, row in enumerate(rows, 1):
            company = row["company"]
            if company in known and settled(known[company], row, boards, providers):
                print(f"[{n}/{len(rows)}] {company}: settled last run")
                continue
            found, empty, tried = None, None, []
            guess = (row.get("provider") or "").strip()
            for provider, pattern in sorted(endpoints, key=lambda e: e[0] != guess):
                for token in candidates(row):
                    url = url_for(pattern, token)
                    if not robots_ok(url):
                        tried.append(f"{provider}:{token}:robots")
                        continue
                    status, body = get(url)
                    tried.append(f"{provider}:{token}:{status}")
                    jobs = jobs_in(provider, body) if status == 200 else None
                    if jobs:
                        found = (provider, token, url_for(pattern, token), body, len(jobs))
                        break
                    if jobs is not None and not empty:
                        empty = (provider, token, url_for(pattern, token), body, 0)
                if found:
                    break
            found = found or empty
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            blank = {"company": company, "provider": "", "token": "", "openings": "", "url": "", "fetched_at": stamp,
                     "board_name": "", "bytes": "", "tried": " ".join(tried)}
            if not found:
                known[company] = dict(blank, status="not found")
                print(f"[{n}/{len(rows)}] {company}: no public board found")
            else:
                provider, token, url, body, count = found
                names = board_names(provider, token, body)
                if any(ex.matches(nm) for nm in names):
                    known[company] = dict(blank, status="dropped")
                    dropped += 1
                    print(f"[{n}/{len(rows)}] one board dropped for the exclusion list, counted at the end")
                else:
                    boards.joinpath(f"{provider}_{token}.json").write_bytes(body)
                    total_bytes += len(body)
                    board_name = sorted(names)[0] if names else ""
                    known[company] = dict(blank, status="ok", provider=provider, token=token, openings=count, url=url,
                                          board_name=board_name, bytes=len(body))
                    print(f"[{n}/{len(rows)}] {company}: {provider}/{token}, {count} openings")
            save()
    except Ceiling:
        save()
        print(f"Stopped at the ceiling of {CEILING} requests. Run it again to pick up where it stopped.")
        return 1
    save()
    ok = sum(1 for c in order if known.get(c, {}).get("status") == "ok")
    print(f"Done in {round(time.time() - started)} s with {SENT['n']} requests. Read {ok} of {len(rows)} boards and saved "
          f"{total_bytes / 1_000_000:.1f} MB to data/raw/ (gitignored). Left out {left_out + dropped + purged} companies "
          f"for the exclusion list, counted and never named.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
