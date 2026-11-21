#!/usr/bin/env python3
"""The owner's machine only. Read the MX and TXT records of each account's domain once, and keep only what names a
vendor.

    python3 owner/dns.py               one read of every matched domain (a minute or two)
    python3 owner/dns.py --dry-run     the domains it would ask about, with nothing sent

The domains come from config/domains.csv, high and medium matches only, for the accounts on the page less any the
exclusion list names. Each lookup goes to the machine's own resolver (the first nameserver in /etc/resolv.conf) over
UDP, and over TCP when an answer is too long for UDP, with a pause between lookups. Nothing secret is kept: the mail
hosts, the hosts an SPF record includes, and the vendors that config/dns_signatures.csv names by a record's prefix.
No verification token and no other TXT text is ever written, only a count of the TXT records. The read goes to
data/raw/dns/<day>.json (gitignored) with the day in Pacific time, and config/sources.json must allow DNS from a terms
check in the last 45 days.
"""
import argparse
import csv
import json
import re
import socket
import struct
import sys
import time
from datetime import date, datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import dnswire, exclusions, stack  # noqa: E402

SOURCES = ROOT.joinpath("config", "sources.json")
DOMAINS = ROOT.joinpath("config", "domains.csv")
RANKING = ROOT.joinpath("data", "out", "ranking.json")
OUT = ROOT.joinpath("data", "raw", "dns")
RESOLV = Path("/etc/resolv.conf")
PAUSE = 0.25
TIMEOUT = 3.0


def allowed(path=None, today=None):
    cfg = json.loads(Path(path or SOURCES).read_text(encoding="utf-8"))
    s = cfg["sources"].get("dns") or {}
    if not s.get("allowed"):
        raise SystemExit("Stopped: config/sources.json doesn't allow DNS.")
    age = ((today or date.today()) - date.fromisoformat(s["checked"])).days
    if age > cfg.get("max_age_days", 45):
        raise SystemExit(f"Stopped: the DNS terms were checked {age} days ago. Run the terms prompt again first.")


def resolver(path=None):
    """The first nameserver the machine uses."""
    path = Path(path or RESOLV)
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    for line in text.splitlines():
        m = re.match(r"\s*nameserver\s+(\S+)", line)
        if m:
            return m.group(1)
    raise SystemExit("Stopped: /etc/resolv.conf names no nameserver, so there's no resolver of the machine's own to ask.")


def lookup(server, name, qtype, sender=None):
    """(rcode, [(type, value)]) for one question, over UDP and over TCP when the answer comes back truncated."""
    ident, packet = dnswire.query(name, qtype)
    send = sender or _send
    for attempt in (1, 2):
        try:
            reply = send(server, packet, tcp=False)
            rcode, truncated, out = dnswire.answers(reply, ident)
            if truncated:
                rcode, _, out = dnswire.answers(send(server, packet, tcp=True), ident)
            return rcode, out
        except (OSError, ValueError):
            if attempt == 2:
                return -1, []
            time.sleep(1)
    return -1, []


def _send(server, packet, tcp):
    family = socket.AF_INET6 if ":" in server else socket.AF_INET
    if not tcp:
        with socket.socket(family, socket.SOCK_DGRAM) as s:
            s.settimeout(TIMEOUT)
            s.sendto(packet, (server, 53))
            return s.recv(65535)
    with socket.create_connection((server, 53), timeout=TIMEOUT) as s:
        s.sendall(struct.pack(">H", len(packet)) + packet)
        size = struct.unpack(">H", _read(s, 2))[0]
        return _read(s, size)


def _read(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise OSError("the resolver closed the connection early")
        data += chunk
    return data


def targets():
    """[(account, domain)] for the high and medium matches still on the page."""
    on_page = {a["account"] for a in json.loads(RANKING.read_text(encoding="utf-8"))["accounts"]}
    ex = exclusions.load()
    with open(DOMAINS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(line for line in f if not line.startswith("#")))
    return [(r["company"], r["domain"]) for r in rows if r["domain"] and r["confidence"] in ("high", "medium")
            and r["company"] in on_page and not ex.matches(r["company"])]


def today():
    tz = ZoneInfo("America/Los_Angeles") if ZoneInfo else None
    return datetime.now(tz).date().isoformat()


def main(argv=None, sender=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="list the domains and stop")
    a = ap.parse_args(argv)
    allowed()
    pairs = targets()
    if a.dry_run:
        for company, domain in pairs:
            print(f"{company}: MX and TXT for {domain}")
        print(f"{len(pairs) * 2} lookups for {len(pairs)} domains through the machine's own resolver.")
        return 0
    server, sigs, day = resolver(), stack.signatures(), today()
    started, out = time.time(), {}
    for n, (company, domain) in enumerate(pairs, 1):
        rec = {"domain": domain, "read_on": day}
        rcodes = []
        for qtype in ("MX", "TXT"):
            rcode, got = lookup(server, domain, qtype, sender)
            rcodes.append(rcode)
            rec[qtype] = [v for t, v in got if t == qtype]
            time.sleep(PAUSE if sender is None else 0)
        read = stack.read_records(rec.pop("MX"), rec.pop("TXT"), sigs)
        status = "ok" if all(r == 0 for r in rcodes) else "no such domain" if 3 in rcodes else "error"
        out[company] = {"domain": domain, "read_on": day, "status": status, **read}
        print(f"[{n}/{len(pairs)}] {company}: {len(read['facts'])} vendor record(s), {status}")
    OUT.mkdir(parents=True, exist_ok=True)
    OUT.joinpath(f"{day}.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    ok = sum(1 for r in out.values() if r["status"] == "ok")
    named = sum(1 for r in out.values() if r["facts"])
    print(f"Done in {round(time.time() - started)} s: {ok} of {len(out)} domains answered and {named} name at least one "
          f"vendor. Wrote data/raw/dns/{day}.json (gitignored) with no verification token and no other TXT text.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
