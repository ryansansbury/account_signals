"""Find public hiring signals in job postings. Every signal keeps the exact sentence it came from, its posting and date.

Title families read the job title: revenue operations, sales operations, CRM, analytics engineering and sales leadership
roles, and founding go-to-market roles. Phrase families read the text of postings in go-to-market, operations, finance,
data and systems roles, which is where a CRM move, a forecasting project, a new territory or a first hire gets written
down. Hiring pace counts go-to-market postings. The stack family records revenue tools a posting names, for the brief's
context, and scores nothing. The rules live in config/signals.json.

The pipeline redacts each posting before anything is found here, and each excerpt is the sentence around the match, cut
at sentence edges to 260 characters at most, so a brief that cites it can be checked against it. An excerpt that holds
hidden characters or phrasing aimed at a model is dropped and counted. A signal's ID is a hash of the account, the
posting, the family and the tool, so a refetch never moves a citation and an excluded account leaves no gap. Within an
account the same sentence in many postings (boilerplate) is one signal, at its freshest posting, with a count of the
postings that carried it. A sentence about the candidate ("experience implementing Salesforce") never counts, and a
family can require a context word in the same sentence.
"""
import hashlib
import json
import re
from pathlib import Path

from engine import textsafety

HERE = Path(__file__).resolve().parent.parent
MAX_EXCERPT = 260
TITLE_FAMILIES = ("revops", "salesops", "crm", "analytics", "leadership")
# Tools that are also everyday words count only beside a stack phrase or another tool in the same sentence.
AMBIGUOUS = {"Close", "Mode", "Hex", "Sigma", "Segment", "Heap", "Excel", "Census", "Clay", "Apollo", "Outreach",
             "Chorus", "Affinity", "Stripe", "Slack", "Notion", "Gong", "Spiff", "Pigment", "Conga", "Domo", "Braze",
             "Seismic", "Iterable", "Looker", "Attio"}
USES = re.compile(r"\b(?:our (?:stack|tools?|tech stack|systems?|platform)|we use|we're using|we rely on|stack includes|"
                  r"tech stack|powered by|built on|tools we use|currently use|currently using|we run on|runs on)\b", re.I)
GENERIC = re.compile(r"\b(?:such as|e\.g\.|for example|or similar|or equivalents?|and the like|etc\b|or other|like)\b",
                     re.I)


def load_config(path=None):
    raw = json.loads(Path(path or HERE.joinpath("config", "signals.json")).read_text(encoding="utf-8"))
    fams = {}
    for name, f in raw["families"].items():
        fams[name] = {"label": f["label"], "where": f["where"], "points": f["points"],
                      "patterns": [re.compile(p, re.I) for p in f.get("patterns", [])],
                      "title_patterns": [re.compile(p, re.I) for p in f.get("title_patterns", [])],
                      "not": re.compile(f["not"], re.I) if f.get("not") else None,
                      "only": re.compile(f["only_titles"], re.I) if f.get("only_titles") else None,
                      "context": re.compile(f["context"], re.I) if f.get("context") else None,
                      "context_titles": re.compile(f["context_titles"], re.I) if f.get("context_titles") else None}
    return {"families": fams, "read": re.compile(raw["read_titles"], re.I), "skip": re.compile(raw["skip_titles"], re.I),
            "pace": re.compile(raw["pace_titles"], re.I),
            "candidate": re.compile(raw["skip_context"], re.I) if raw.get("skip_context") else None}


def as_label(label):
    """A family's label inside a sentence: "Revenue operations role" becomes "revenue operations role," and "CRM
    role" stays as it is."""
    return label if label.split()[0].isupper() else label[:1].lower() + label[1:]


def load_tools(path=None):
    path = Path(path or HERE.joinpath("config", "tools.txt"))
    names = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    return sorted(names, key=len, reverse=True)


def readable(title, cfg):
    """True when a posting's text is read for phrases: a go-to-market or adjacent role, never a skipped one."""
    return bool(cfg["read"].search(title or "")) and not cfg["skip"].search(title or "")


def excerpt(text, start, end):
    """The sentence around a match, trimmed to MAX_EXCERPT characters with ellipses where it was cut."""
    left = max(text.rfind(". ", 0, start), text.rfind("? ", 0, start), text.rfind("! ", 0, start))
    left = 0 if left < 0 else left + 2
    stops = [i for i in (text.find(". ", end), text.find("? ", end), text.find("! ", end)) if i >= 0]
    right = min(stops) + 1 if stops else len(text)
    if right - left <= MAX_EXCERPT:
        return text[left:right].strip()
    half = (MAX_EXCERPT - (end - start)) // 2
    a = max(left, start - half)
    b = min(right, end + half)
    if a > left:
        a = text.find(" ", a) + 1 or a
    if b < right:
        cut = text.rfind(" ", a, b)
        b = cut if cut > end else b
    return ("…" if a > left else "") + text[a:b].strip() + ("…" if b < right else "")


def strength(sentence, tools):
    """'uses' when a tool reads like part of their own stack, 'lists' when it's one of several in a requirement."""
    if USES.search(sentence):
        return "uses"
    named = {t for t in tools if re.search(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", sentence)}
    if len(named) >= 3 or GENERIC.search(sentence):
        return "lists"
    return "uses"


def _stack(text, tools):
    """[(tool, start, end)] for each tool named, first mention only, longest names first."""
    out, taken = [], []
    for t in tools:
        for m in re.finditer(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", text):
            if any(a <= m.start() < b for a, b in taken):
                continue
            out.append((t, m.start(), m.end()))
            taken.append((m.start(), m.end()))
            break
    return out


def find(posting, cfg, tools, dropped=None):
    """[(family, tool, matched, excerpt, strength)] for one posting. dropped counts excerpts set aside as suspicious."""
    if posting.get("evergreen"):
        return []
    title, text = posting.get("title") or "", posting.get("text") or ""
    fams, out = cfg["families"], []
    for name in TITLE_FAMILIES:
        f = fams[name]
        if f["not"] and f["not"].search(title):
            continue
        m = next((m for p in f["patterns"] for m in [p.search(title)] if m), None)
        if m:
            out.append((name, "", m.group(0), title, ""))
    f = fams["first_hire"]
    m = next((m for p in f["title_patterns"] for m in [p.search(title)] if m), None)
    if m:
        out.append(("first_hire", "", m.group(0), title, ""))
    if cfg["pace"].search(title) and not cfg["skip"].search(title):
        out.append(("pace", "", "", title, ""))
    if not readable(title, cfg) or not text:
        return out
    for name, f in fams.items():
        if f["where"] not in ("text", "title_or_text") or (name == "first_hire" and m):
            continue
        if f["only"] and not f["only"].search(title):
            continue
        hits = sorted((h for p in f["patterns"] for h in p.finditer(text)), key=lambda h: (h.start(), -h.end()))
        for hit in hits:
            ex = excerpt(text, hit.start(), hit.end())
            if cfg.get("candidate") and cfg["candidate"].search(ex):
                continue
            needs = f["context"] and not (f["context_titles"] and f["context_titles"].search(title))
            if needs and not f["context"].search(ex):
                continue
            if textsafety.suspicious(ex):
                if dropped is not None:
                    dropped["suspicious"] = dropped.get("suspicious", 0) + 1
                break
            out.append((name, "", hit.group(0), ex, ""))
            break
    for tool, a, b in _stack(text, tools):
        ex = excerpt(text, a, b)
        if tool in AMBIGUOUS and not (USES.search(ex) or any(
                t not in AMBIGUOUS and re.search(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", ex) for t in tools)):
            continue
        if textsafety.suspicious(ex):
            if dropped is not None:
                dropped["suspicious"] = dropped.get("suspicious", 0) + 1
            continue
        out.append(("stack", tool, tool, ex, strength(ex, tools)))
    return out


def sid(account, posting_id, family, tool):
    return "s" + hashlib.sha1(f"{account}|{posting_id}|{family}|{tool}".encode()).hexdigest()[:10]


def extract(account, postings, read_on, cfg, tools, dropped=None):
    """Every signal for one account, with boilerplate folded: [{sid, account, family, label, tool, matched, excerpt,
    strength, posting_id, title, url, posted, date_kind, temporary, carried, read_on}]."""
    found = {}
    fams = cfg["families"]
    for p in postings:
        for family, tool, matched, ex, level in find(p, cfg, tools, dropped):
            text_family = fams[family]["where"] in ("text", "title_or_text", "stack") and ex != p["title"]
            key = (family, tool, " ".join(ex.lower().split())) if text_family else (family, tool, p["id"])
            rec = {"account": account, "family": family, "label": fams[family]["label"], "tool": tool,
                   "matched": matched, "excerpt": ex, "strength": level, "posting_id": p["id"], "title": p["title"],
                   "url": p["url"], "posted": p["posted"].isoformat() if p.get("posted") else "",
                   "date_kind": p.get("date_kind", ""), "temporary": p.get("employment") == "temporary",
                   "carried": 1, "read_on": read_on}
            old = found.get(key)
            if old is None:
                found[key] = rec
                continue
            rec["carried"] = old["carried"] + 1
            if (rec["posted"], rec["posting_id"]) > (old["posted"], old["posting_id"]):
                found[key] = rec
            else:
                old["carried"] = rec["carried"]
    out = list(found.values())
    for s in out:
        s["sid"] = sid(account, s["posting_id"], s["family"], s["tool"])
    out.sort(key=lambda s: (s["family"], s["posted"], s["sid"]), reverse=False)
    return out
