"""The last check for people's details in everything that ships: the page's data, the snapshot, WORDS.md, the README
and the docs.

It looks for what redaction removes (email addresses, phone numbers, social handles, likely names) plus any link that
doesn't go to a job board, this project's own pages or a cited public source. It reports counts and line numbers, never
the text it found, and the build stops on any hit. A posting's own URL, exactly as the snapshot records it, is
allowed wherever it appears, since many employers host their boards on their own careers domains. Code files get the email, phone and link checks only, since a
stylesheet's @media or a regular expression isn't a person. The tests' made-up people never ship in the page, so the
tests folder isn't scanned here.
"""
import re
from pathlib import Path
from urllib.parse import urlsplit

from engine import redact as R

ALLOWED_HOSTS = {
    "job-boards.greenhouse.io", "boards.greenhouse.io", "boards-api.greenhouse.io", "jobs.lever.co", "api.lever.co",
    "jobs.ashbyhq.com", "api.ashbyhq.com", "ryansansbury.com", "www.ryansansbury.com", "github.com",
    "www.linkedin.com", "linkedin.com", "www.census.gov", "census.gov", "www2.census.gov", "polyformproject.org",
    "docs.greenhouse.io", "developers.ashbyhq.com", "api.anthropic.com", "api.openai.com", "127.0.0.1", "localhost",
    "www.w3.org", "www.sec.gov", "data.sec.gov",
    # The vendors' own documentation behind config/dns_signatures.csv (the 11/11 terms check).
    "help.salesforce.com", "knowledge.hubspot.com", "experienceleague.adobe.com", "learn.microsoft.com",
    "support.zendesk.com", "support.freshdesk.com", "support.google.com", "www.twilio.com", "docs.aws.amazon.com",
    "help.mailgun.com", "documentation.mailgun.com", "postmarkapp.com", "support.greenhouse.io", "helpx.adobe.com",
    "support.atlassian.com",
}
OWN = {"linkedin.com/in/ryansansbury", "github.com/ryansansbury"}
URL = re.compile(r"https?://[^\s<>\"'`)\]\\]+", re.I)
DATA_SUFFIXES = (".md", ".json", ".jsonl", ".csv", ".txt", ".html")
DATA_FILES = ("data.js",)


def _link_ok(url):
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return True  # a pattern in code such as a regular expression, which no one can follow
    if "{" in host:
        return True  # a template in code ("https://{host}/robots.txt"), which no one can follow
    if host not in ALLOWED_HOSTS:
        return False
    if host.endswith("linkedin.com"):
        return any(o in url.lower() for o in OWN)
    if host == "github.com":
        return any(p in url.lower() for p in ("github.com/ryansansbury", "github.com/topojson", "github.com/lever/postings-api"))
    return True


def findings(text, data=True, keep=(), redactor=None, allowed_urls=frozenset()):
    """{kind: [line numbers]} for everything in the text that looks like a person's details or a stray link."""
    r = redactor or R.Redactor()
    keep = {w.lower() for k in keep for w in re.findall(r"[A-Za-z0-9']+", k or "")} | {"ryan", "sansbury"}
    out = {"email": [], "phone": [], "link": [], "handle": [], "name": []}
    for n, line in enumerate(text.splitlines(), 1):
        if R.EMAIL.search(line):
            out["email"].append(n)
        if R.PHONE.search(line):
            out["phone"].append(n)
        if any(u not in allowed_urls and not _link_ok(u) for u in URL.findall(line)):
            out["link"].append(n)
        if not data:
            continue
        if R.HANDLE.search(line):
            out["handle"].append(n)
        for m in R.RUN.finditer(line):
            if r.names_in_run(m.group(0), keep)[1]:
                out["name"].append(n)
                break
    return {k: v for k, v in out.items() if v}


def scan(paths, keep=(), redactor=None, allowed_urls=frozenset()):
    """A line per file with anything that looks like a person's details, by kind and line number."""
    r = redactor or R.Redactor()
    problems = []
    for p in map(Path, paths):
        if not p.exists():
            continue
        data = p.suffix.lower() in DATA_SUFFIXES or p.name in DATA_FILES
        found = findings(p.read_text(encoding="utf-8", errors="ignore"), data=data, keep=keep, redactor=r,
                         allowed_urls=allowed_urls)
        if found:
            parts = [f"{len(v)} {k} line(s) (first at line {v[0]})" for k, v in found.items()]
            problems.append(f"{p.name} may hold a person's details: " + ", ".join(parts))
    return problems
