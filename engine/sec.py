"""The SEC's side of an account: how its filings are read and how a company on the page is matched to an SEC identity.

owner/sec.py does the reading, from the owner's machine. This module holds the rules, so the tests can run them on
made-up companies with no network:

- company_tickers.json gives every company with a ticker, its CIK and its name;
- a quarterly Form D data set gives every Form D filed that quarter, and only three of its tables are ever read: the
  filing (its date and type), the issuer (its CIK, name, city and state) and the offering (the date of first sale, the
  amounts offered and sold, and the industry group). The tables that name people, the related persons, the signers and
  the recipients, are never opened;
- a match compares names after the exclusion list's own normalizing (legal suffixes dropped, and the core of a name with
  generic endings such as Labs or Technologies dropped too). A ticker by the exact name is high confidence, since a
  public company's name is unique on the SEC's list. A Form D filer by the exact name is high when it filed from a state
  where the account hires, medium when the account's postings name no state to check, and unmatched when it filed from
  somewhere else, since that's most often another company by the same name. An account whose name fits more than one
  identity stays unmatched instead of guessed.

Standard library only.
"""
import csv
import io
import json
import re
from datetime import datetime

from engine import exclusions

READ_TABLES = ("FORMDSUBMISSION", "ISSUERS", "OFFERING")
PEOPLE_TABLES = ("RELATEDPERSONS", "SIGNATURES", "RECIPIENTS")
DATE_FORMATS = ("%Y-%m-%d", "%d-%b-%Y", "%m/%d/%Y", "%Y%m%d", "%d-%b-%y")


def iso(value):
    """A date as YYYY-MM-DD from any form the data sets use, or "" when it isn't a date."""
    value = (value or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def amount(value):
    """A dollar amount as an int, or None for "Indefinite", a blank or anything else that isn't a number."""
    digits = re.sub(r"[,$\s]", "", value or "")
    return int(float(digits)) if re.fullmatch(r"\d+(?:\.\d+)?", digits) else None


def tickers(raw):
    """[{cik, ticker, name}] from company_tickers.json."""
    data = json.loads(raw)
    rows = data.values() if isinstance(data, dict) else data
    return [{"cik": int(r["cik_str"]), "ticker": r.get("ticker", ""), "name": r.get("title", "")} for r in rows]


def table_name(member):
    return re.sub(r"\.(tsv|txt)$", "", member.rsplit("/", 1)[-1], flags=re.I).upper()


def form_d_rows(zipfile_obj):
    """[{accession, filed, type, cik, name, city, state, first_sale, offered, sold, industry}] for one data set, the
    primary issuer of each filing only. The tables that name people are never opened."""
    tables = {}
    for member in zipfile_obj.namelist():
        name = table_name(member)
        if name in PEOPLE_TABLES or name not in READ_TABLES:
            continue
        with zipfile_obj.open(member) as f:
            text = io.TextIOWrapper(f, encoding="utf-8", errors="replace", newline="")
            tables[name] = list(csv.DictReader(text, delimiter="\t"))
    subs = {r.get("ACCESSIONNUMBER"): r for r in tables.get("FORMDSUBMISSION", [])}
    offers = {r.get("ACCESSIONNUMBER"): r for r in tables.get("OFFERING", [])}
    out = []
    for r in tables.get("ISSUERS", []):
        if (r.get("IS_PRIMARYISSUER_FLAG") or "YES").upper() not in ("YES", "Y", "TRUE", "1"):
            continue
        acc = r.get("ACCESSIONNUMBER")
        s, o = subs.get(acc, {}), offers.get(acc, {})
        if (s.get("TESTORLIVE") or "LIVE").upper() == "TEST":
            continue
        out.append({"accession": acc, "filed": iso(s.get("FILING_DATE")), "type": s.get("SUBMISSIONTYPE", ""),
                    "cik": int(r["CIK"]) if (r.get("CIK") or "").strip().isdigit() else None,
                    "name": r.get("ENTITYNAME", ""), "city": (r.get("CITY") or "").strip().title(),
                    "state": (r.get("STATEORCOUNTRY") or "").strip().upper(),
                    "first_sale": iso(o.get("SALE_DATE")), "offered": amount(o.get("TOTALOFFERINGAMOUNT")),
                    "sold": amount(o.get("TOTALAMOUNTSOLD")), "industry": o.get("INDUSTRYGROUPTYPE", "")})
    return out


def keys(name):
    """(full, core): a name's normalized form and its core, both squeezed of spaces."""
    return (re.sub(r"\s+", "", exclusions.full(name) or ""), re.sub(r"\s+", "", exclusions.core(name) or ""))


def strength(a, b):
    """2 when the full names match, 1 when only a core does, and 0 otherwise. Names under three letters never match."""
    (af, ac), (bf, bc) = a, b
    if len(af) >= 3 and af == bf:
        return 2
    if len(ac) >= 3 and (ac == bc or ac == bf or af == bc):
        return 1
    return 0


def states_of(account):
    """The US states where an account's postings name a city, from the ranking."""
    out = {c.get("state", "") for c in account.get("cities", []) if isinstance(c, dict)}
    if account.get("hub"):
        out.add(account["hub"].get("state", ""))
    return {s.upper() for s in out if s}


def index(ticker_rows, form_d_rows_all):
    """Every ticker and Form D filer by its full and core name, normalized once, so each match is a lookup."""
    by = {}
    for t in ticker_rows:
        k = keys(t["name"])
        for key in set(k):
            by.setdefault(key, []).append(("ticker", t, k))
    for f in form_d_rows_all:
        if f["cik"]:
            k = keys(f["name"])
            for key in set(k):
                by.setdefault(key, []).append(("form d", f, k))
    return by


def match(account, ticker_rows, form_d_rows_all, by=None):
    """{cik, name, source, ticker, confidence, evidence} for one account, or an unmatched row. A full name that matches
    beats a core that matches. A core alone counts only when the SEC's address sits in a state where the account hires.
    Pass index() as by to match many accounts against the same rows quickly."""
    want, states = keys(account["account"]), states_of(account)
    by = by if by is not None else index(ticker_rows, form_d_rows_all)
    found, seen = {}, set()
    for key in {k for k in want if len(k) >= 3}:
        for source, row, k in by.get(key, []):
            if id(row) in seen:
                continue
            seen.add(id(row))
            s = strength(want, k)
            if not s:
                continue
            c = found.setdefault(row["cik"], {"name": row["name"], "source": source, "ticker": row.get("ticker", ""),
                                              "states": set(), "filings": 0, "strength": 0})
            c["strength"] = max(c["strength"], s)
            if source == "form d":
                c["states"].add(row["state"])
                c["filings"] += 1
    if not found:
        return {"cik": None, "confidence": "unmatched", "evidence": ["no name in the tickers or the Form D data sets"]}
    best = max(c["strength"] for c in found.values())
    pool = {cik: c for cik, c in found.items() if c["strength"] == best}
    near = {cik: c for cik, c in pool.items() if c["states"] & states}
    if best == 1 and not near:
        return {"cik": None, "confidence": "unmatched", "evidence": ["only a shortened name fits and not in its states"]}
    pool = near or pool
    if len(pool) > 1:
        return {"cik": None, "confidence": "unmatched",
                "evidence": [f"the name fits {len(pool)} identities" + (" in its states" if near else "")]}
    cik, c = next(iter(pool.items()))
    if c["source"] == "ticker" and best == 2:
        confidence = "high"  # a public company's exact name is unique on the SEC's ticker list
    elif near:
        confidence = "high" if best == 2 else "medium"
    elif not states:
        confidence = "medium"  # postings that name no US state leave nothing to check the filing's state against
    else:
        return {"cik": None, "confidence": "unmatched",
                "evidence": ["the only filer by its name sits in a state where it doesn't hire"]}
    evidence = ("a ticker by the same name" if c["source"] == "ticker" else
                f"{c['filings']} Form D filing{'s' if c['filings'] != 1 else ''} by the same name")
    if best == 1:
        evidence = evidence.replace("the same name", "a shortened form of the name")
    evidence = [evidence] + (["filed from a state where it hires"] if near else [])
    return {"cik": cik, "name": c["name"], "source": c["source"], "ticker": c["ticker"], "confidence": confidence,
            "evidence": evidence}


def confirm(identity, submissions, account, domain=""):
    """The match after the SEC's own record of the company: a website on file that is the account's domain, or a
    business address in a state where it hires, turns a medium match high."""
    if not identity.get("cik"):
        return identity
    out = dict(identity, evidence=list(identity["evidence"]))
    site = (submissions.get("website") or "").lower()
    state = (((submissions.get("addresses") or {}).get("business") or {}).get("stateOrCountry") or "").upper()
    found = []
    if domain and site and domain.lower() in site:
        found.append("its website on file is the account's own domain")
    if state and state in states_of(account) and "filed from a state where it hires" not in out["evidence"]:
        found.append("its business address is in a state where it hires")
    if found and out["confidence"] == "medium":
        out["confidence"] = "high"
    out["evidence"] += found
    out["industry_code"] = submissions.get("sicDescription") or ""
    return out


def form_d_dates(submissions):
    """Every Form D and amendment a submissions file lists, as [(filed, form, accession)]."""
    recent = (submissions.get("filings") or {}).get("recent") or {}
    forms, dates, accs = recent.get("form", []), recent.get("filingDate", []), recent.get("accessionNumber", [])
    return [(d, f, a) for f, d, a in zip(forms, dates, accs) if f in ("D", "D/A")]
