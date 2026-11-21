"""Each account's own web domain, from what its postings say, with the evidence behind it and a confidence.

    python3 -m engine.domains          (from the build folder, on a machine that holds the boards as read)

A domain is evidence when a posting's own address sits on it (a board the company hosts on its careers site), or when a
posting links to it or names it. The hosts of job boards, social sites, government and school sites, and link shorteners
never count. The domain that wins is the one whose name matches the company's name or its board token, and among
those the one most of the account's postings point to. It's high confidence when its name matches and the company
hosts its board there or more than one posting points to it. It's medium when its name matches on one posting alone,
or when the company hosts its board on a domain its name doesn't match. Anything else stays unmatched instead of
guessed. Phase 2's DNS read and Phase 3's SEC match start from config/domains.csv,
which this writes with counts only and no posting text. Standard library only.
"""
import csv
import html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import exclusions  # noqa: E402

RAW_BOARDS = HERE.joinpath("data", "raw", "boards")
BOARDS = HERE.joinpath("data", "snapshot", "boards.csv")
RANKING = HERE.joinpath("data", "out", "ranking.json")
OUT = HERE.joinpath("config", "domains.csv")
FIELDS = ["company", "domain", "confidence", "name_match", "own_host", "links", "mentions"]

# Hosts that are never a company's own: job boards, social sites, maps and video, link shorteners, and the like.
NOT_OWN = {
    "greenhouse.io", "lever.co", "ashbyhq.com", "workday.com", "myworkdayjobs.com", "icims.com", "smartrecruiters.com",
    "jobvite.com", "bamboohr.com", "workable.com", "linkedin.com", "glassdoor.com", "indeed.com", "ziprecruiter.com",
    "builtin.com", "wellfound.com", "angel.co", "twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com",
    "youtu.be", "tiktok.com", "medium.com", "github.com", "google.com", "goo.gl", "bit.ly", "tinyurl.com", "lnkd.in",
    "ow.ly", "t.co", "apple.com", "microsoft.com", "adobe.com", "amazon.com", "wikipedia.org", "vimeo.com",
    "forms.gle", "docs.google.com", "calendly.com", "zoom.us", "e-verify.gov", "eeoc.gov", "dol.gov", "uscis.gov",
    "w3.org", "schema.org", "gstatic.com", "googleapis.com", "cloudfront.net", "amazonaws.com", "salesforce.com",
    "hubspot.com", "glassdoor.co.uk", "crunchbase.com", "forbes.com", "inc.com", "fastcompany.com", "bloomberg.com",
}
NOT_OWN_ENDINGS = (".gov", ".mil", ".edu")
TWO_PART = {"co.uk", "com.au", "co.nz", "co.in", "com.br", "com.mx", "co.jp", "com.sg", "co.za", "com.cn"}
HOST = re.compile(r"\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|io|ai|co|net|org|health|energy|us|app|tech|"
                  r"dev|bio|care|inc|so|xyz|team|works|farm|eco|solar|global))\b", re.I)
HREF = re.compile(r"""href\s*=\s*["']https?://([^/"'?#:]+)""", re.I)


def registrable(host):
    """The domain a company registers: www.careers.example.com and example.com both give example.com. Anything before
    an @ (a mailbox in a link) is dropped first."""
    parts = (host or "").lower().split("@")[-1].strip(".").split(".")
    if len(parts) < 2:
        return ""
    if ".".join(parts[-2:]) in TWO_PART and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def counts(domain):
    """True when a domain can be a company's own: a name with a letter in it, on no host that never counts."""
    label = (domain or "").split(".")[0]
    return (bool(re.search(r"[a-z]", label)) and domain not in NOT_OWN and not domain.endswith(NOT_OWN_ENDINGS) and
            bool(re.search(r"\.[a-z]{2,}$", domain)))


def squeeze(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def name_match(domain, company, token=""):
    """The domain's name holds the company's name or board token, or the other way round, ignoring a leading "the"
    and generic endings such as Labs, Health or Technologies."""
    label = squeeze(domain.split(".")[0])
    if not label:
        return False
    names = {squeeze(company), squeeze(re.sub(r"^the\s+", "", company or "", flags=re.I)), squeeze(token),
             squeeze(exclusions.core(company) if hasattr(exclusions, "core") else "")}
    names = {n for n in names if len(n) >= 3}
    return any(label == n or label in n or n in label for n in names)


def text_of(provider, job):
    """A posting's own address and the text its links and mentions come from."""
    if provider == "lever":
        parts = [job.get("description") or "", job.get("additional") or ""]
        parts += [x.get("content") or "" for x in job.get("lists") or [] if isinstance(x, dict)]
        return "", html.unescape(" ".join(parts))
    return job.get("absolute_url") or "", html.unescape(job.get("content") or "")


def evidence(provider, jobs):
    """{domain: {own_host, links, mentions}} counted once per posting."""
    found = defaultdict(Counter)
    for job in jobs:
        if not isinstance(job, dict):
            continue
        own, text = text_of(provider, job)
        seen = set()
        host = registrable(re.sub(r"^https?://", "", own).split("/")[0].split(":")[0]) if own else ""
        if counts(host):
            found[host]["own_host"] += 1
            seen.add(host)
        linked = {registrable(h) for h in HREF.findall(text)}
        for d in linked:
            if counts(d):
                found[d]["links"] += 1
        named = {registrable(m.group(1)) for m in HOST.finditer(re.sub(r"<[^>]+>", " ", text))}
        for d in named - linked:
            if counts(d):
                found[d]["mentions"] += 1
    return found


def pick(company, token, found):
    """(domain, confidence, name_match, counts) for the best candidate, or an unmatched row."""
    if not found:
        return "", "unmatched", False, Counter()
    total = lambda d: sum(found[d].values())  # noqa: E731
    best = max(found, key=lambda d: (name_match(d, company, token), found[d]["own_host"] > 0, total(d), d))
    matched, own, many = name_match(best, company, token), found[best]["own_host"] > 0, total(best) > 1
    if matched and (own or many):
        return best, "high", True, found[best]
    if matched or (own and many):
        return best, "medium", matched, found[best]
    return "", "unmatched", False, Counter()


def main():
    ranking = json.loads(RANKING.read_text(encoding="utf-8"))["accounts"]
    with open(BOARDS, newline="", encoding="utf-8") as f:
        where = {r["company"]: (r["provider"], r["token"]) for r in csv.DictReader(f)}
    rows = []
    for a in sorted(ranking, key=lambda x: x["account"]):
        provider, token = where[a["account"]]
        raw = json.loads(RAW_BOARDS.joinpath(f"{provider}_{token}.json").read_text(encoding="utf-8"))
        jobs = raw if provider == "lever" else raw.get("jobs", [])
        domain, confidence, matched, c = pick(a["account"], token, evidence(provider, jobs))
        rows.append({"company": a["account"], "domain": domain, "confidence": confidence,
                     "name_match": "yes" if matched else "no", "own_host": c["own_host"], "links": c["links"],
                     "mentions": c["mentions"]})
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        f.write("# Each account's own web domain from its postings (engine/domains.py). Counts of postings only.\n")
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    tally = Counter(r["confidence"] for r in rows)
    print(f"Matched {len(rows) - tally['unmatched']} of {len(rows)} accounts to a domain: {tally['high']} high, "
          f"{tally['medium']} medium, and {tally['unmatched']} unmatched. Wrote config/domains.csv.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
