"""An account's stack: the tools its postings name and the vendors its public DNS records name, each with its evidence.

Two sources, each read for what it can and can't say:
- a posting that names a tool, where "uses" means the sentence reads like part of the team's own stack and "lists" means
  the tool is one of several in a requirement;
- a domain's DNS on the day it was read. An SPF include names a vendor allowed to send the domain's mail, and a mail
  host names who handles it, so both speak to the mail that flows today. A verification record says only that a vendor
  was set up at some point, since vendors such as Microsoft and Adobe say it may come out after setup. No verification
  token is ever kept, only the vendor its prefix names, and other TXT records are counted and dropped.

stack() joins the two by tool and group, and agreement() is the check that the two sources say the same thing where
both speak to the CRM. Standard library only.
"""
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SIGNATURES = HERE.joinpath("config", "dns_signatures.csv")
CATEGORIES = HERE.joinpath("config", "stack_categories.json")
CRMS = ("Salesforce", "HubSpot", "Microsoft Dynamics", "Dynamics 365", "Microsoft Dynamics 365", "Zoho CRM", "Pipedrive")
SAME = {"Sales Cloud": "Salesforce", "Service Cloud": "Salesforce", "Dynamics 365": "Microsoft Dynamics",
        "Microsoft Dynamics 365": "Microsoft Dynamics", "Account Engagement": "Pardot"}


def signatures(path=None):
    with open(path or SIGNATURES, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def categories(path=None):
    cfg = json.loads(Path(path or CATEGORIES).read_text(encoding="utf-8"))["categories"]
    return {tool: group for group, tools in cfg.items() for tool in tools}


def _host_matches(host, suffix):
    host, suffix = host.lower().rstrip("."), suffix.lower().rstrip(".")
    return host == suffix or host.endswith("." + suffix) or host.endswith(suffix)


def spf_includes(txt_values):
    """The hosts an SPF record includes or redirects to, top level only."""
    out = []
    for v in txt_values:
        if v.lower().startswith("v=spf1"):
            for token in v.split():
                m = re.match(r"(?:include:|redirect=)(\S+)$", token, re.I)
                if m:
                    out.append(m.group(1).lower())
    return out


def read_records(mx_hosts, txt_values, sigs=None):
    """{facts, spf, txt_records, mx_hosts}. Facts name a vendor, its group, what kind of record named it and the
    evidence in words. Nothing secret is kept: hosts from MX and SPF, and for verification records the prefix alone."""
    sigs = sigs if sigs is not None else signatures()
    includes, facts, seen = spf_includes(txt_values), [], set()

    def add(sig, kind, evidence):
        key = (sig["vendor"], kind)
        if key not in seen:
            seen.add(key)
            facts.append({"vendor": sig["vendor"], "category": sig["category"], "kind": kind, "evidence": evidence,
                          "confidence": sig["confidence"], "source": sig["source"]})

    for host in includes:
        for sig in sigs:
            if sig["kind"] == "spf" and _host_matches(host, sig["match"]):
                add(sig, "spf", f"its SPF record includes {host}")
    for host in mx_hosts:
        for sig in sigs:
            if sig["kind"] == "mx" and _host_matches(host, sig["match"]):
                add(sig, "mx", f"its mail host is {host}")
    for value in txt_values:
        for sig in sigs:
            if sig["kind"] == "txt" and value.startswith(sig["match"]):
                add(sig, "txt", f"a verification record with the {sig['match']} prefix")
    return {"facts": facts, "spf": any(v.lower().startswith("v=spf1") for v in txt_values),
            "txt_records": len(txt_values), "mx_hosts": len(mx_hosts)}


def from_postings(signals, groups=None):
    """{tool: {category, uses, lists, url}} from an account's stack signals: how many postings name it each way, and
    the link of the strongest one."""
    groups = groups if groups is not None else categories()
    out = {}
    for s in signals:
        if s.get("family") != "stack" or not s.get("tool"):
            continue
        tool = SAME.get(s["tool"], s["tool"])
        t = out.setdefault(tool, {"category": groups.get(s["tool"], groups.get(tool, "other")), "uses": 0, "lists": 0,
                                  "url": "", "uses_url": ""})
        uses = s.get("strength") == "uses"
        t["uses" if uses else "lists"] += 1
        t["url"] = t["url"] or s.get("url", "")
        if uses:
            t["uses_url"] = t["uses_url"] or s.get("url", "")
    for t in out.values():
        t["url"] = t.pop("uses_url") or t["url"]
    return out


def stack(signals, dns=None, groups=None):
    """{tool or vendor: {category, postings, dns}} with each source's own evidence, joined by name."""
    out = {}
    for tool, t in from_postings(signals, groups).items():
        out[tool] = {"category": t["category"], "postings": t, "dns": []}
    for fact in (dns or {}).get("facts", []):
        name = SAME.get(fact["vendor"], fact["vendor"])
        entry = out.setdefault(name, {"category": fact["category"], "postings": None, "dns": []})
        entry["dns"].append(fact)
    return out


def crm(entry_map):
    """(the CRMs the postings name, the CRMs the DNS names)."""
    posts = {n for n, e in entry_map.items() if e["postings"] and n in CRMS}
    dns = {n for n, e in entry_map.items() if e["dns"] and n in CRMS}
    return posts, dns


def agreement(stacks):
    """How often the postings and the DNS agree on the CRM where both name one: (both name one, they share one)."""
    both = share = 0
    for entry_map in stacks.values():
        posts, dns = crm(entry_map)
        if posts and dns:
            both += 1
            share += bool(posts & dns)
    return both, share
