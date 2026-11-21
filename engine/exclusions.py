"""The private exclusion list: no company on it is read, scored, mapped or shipped, and nothing here ever names one.

An owner script that never ships, owner/exclusions.py, writes private/exclusions.txt on the owner's machine. This
module only reads that file, matches company names against it and counts mentions of them in text. It reports counts and never a
name, and its tests use made-up names.

A match leans toward leaving a company out, since a wrong match only makes the universe a little smaller:
- names are compared after normalizing (ASCII, lower case, "&" as "and," punctuation and notes in parentheses dropped,
  a leading "the" dropped, and legal suffixes such as Inc, LLC and Corp stripped);
- the core of a name also drops trailing generic words such as Labs, Technologies and AI;
- two names match when their full forms or cores are equal with the spaces squeezed out, when the shorter core (four
  letters or more) is the first whole words of the longer one, when a board token equals a squeezed name, or when
  one name mentions the other the way the text scan counts a mention (11/20).

A mention in text is a whole-word hit on an excluded core that starts with a capital letter where it's found, so "ramp
up" never counts for a company named for the word. Tools named in config/tools.txt are set aside in text (decision D6, 11/9),
since a tool maker on the list may appear as a quoted tool but never as an account, and so are the job board providers
in config/sources.txt, which every page has to name as its sources, and the office and cloud products in
config/vendors.txt. A tool's own name is set aside whole, so its maker named inside it is never a mention.
"""
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DEFAULT = HERE.joinpath("private", "exclusions.txt")
TOOLS = HERE.joinpath("config", "tools.txt")
SOURCES = HERE.joinpath("config", "sources.txt")
VENDORS = HERE.joinpath("config", "vendors.txt")
PLACES = HERE.joinpath("config", "places.txt")
LEGAL = {"inc", "incorporated", "llc", "llp", "lp", "ltd", "limited", "corp", "corporation", "co", "company", "plc",
         "pbc", "gmbh", "holdings", "sa", "ag", "bv", "pty"}
GENERIC = {"labs", "lab", "technologies", "technology", "tech", "software", "systems", "solutions", "ai", "io", "hq",
           "app", "group", "global", "usa", "us"}


def _ascii(text):
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()


def full(name):
    """The normalized name: 'The Quorvex Company, Inc.' becomes 'quorvex'."""
    s = _ascii(name).replace("&", " and ")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"['’`]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    words = s.split()
    if len(words) > 1 and words[0] == "the":
        words = words[1:]
    while len(words) > 1 and words[-1] in LEGAL:
        words.pop()
    return " ".join(words)


def core(name):
    """The normalized name without trailing generic words: 'Zarnoth Labs' becomes 'zarnoth'."""
    words = full(name).split()
    while len(words) > 1 and words[-1] in GENERIC:
        words.pop()
    return " ".join(words)


def squeeze(text):
    return text.replace(" ", "")


def variants(name):
    """A normalized name squeezed, with and without a standalone "and," so "Plinth & Moor" meets "Plinth Moor"."""
    words = name.split()
    return {squeeze(name), "".join(w for w in words if w != "and") or squeeze(name)}


WORD = re.compile(r"[A-Za-z0-9]+")


def _flat(text):
    """Text as plain ASCII words, with apostrophes dropped and "&" read as "and," the way names are normalized."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").replace("'", "") \
        .replace("&", " and ")


def read_names(path):
    path = Path(path)
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


class Exclusions:
    def __init__(self, names, tools=(), present=True):
        self.present = present
        self.entries = []
        seen = set()
        for n in names:
            f, c = full(n), core(n)
            if f and f not in seen:
                seen.add(f)
                self.entries.append((f, c))
        self.fulls = set().union(*(variants(f) for f, _ in self.entries)) if self.entries else set()
        self.cores = set().union(*(variants(c) for _, c in self.entries if len(squeeze(c)) >= 3)) \
            if self.entries else set()
        self.prefixes = [c.split() for _, c in self.entries if len(squeeze(c)) >= 4]
        allowed = {squeeze(core(t)) for t in tools}
        self._said = set()  # each excluded core as words, with and without a standalone "and"
        for _, c in self.entries:
            if len(squeeze(c)) >= 3 and squeeze(c) not in allowed:
                self._said.add(c)
                if " and " in c:
                    self._said.add(c.replace(" and ", " "))
        self._longest = max((len(c.split()) for c in self._said), default=0)
        # A tool's own name is set aside whole, so a maker named inside it ("Google Sheets") isn't a mention.
        self._tools = {}
        for words in sorted({tuple(WORD.findall(_flat(t))) for t in tools if t}, key=len, reverse=True):
            if words:
                self._tools.setdefault(words[0], []).append(words)

    def __len__(self):
        return len(self.entries)

    def matches(self, name, tokens=()):
        """True when a company (by its name or any of its board tokens) is on the list."""
        f, c = full(name), core(name)
        if f and variants(f) & self.fulls:
            return True
        if len(squeeze(c)) >= 3 and variants(c) & self.cores:
            return True
        words = c.split()
        for ex in self.prefixes:
            short, long_ = (words, ex) if len(words) <= len(ex) else (ex, words)
            if short and long_[:len(short)] == short and len(squeeze(" ".join(short))) >= 4:
                return True
        for t in tokens:
            t = re.sub(r"[^a-z0-9]", "", _ascii(t))
            if t and (t in self.fulls or t in self.cores):
                return True
        # A company whose own name mentions one on the list is left out too (11/20), so the account never shows a name
        # the final scan would refuse.
        return bool(self.mentions(name))

    def mentions(self, text):
        """How many times the text names an excluded company as a proper noun. It never says which one."""
        if not self._said or not text:
            return 0
        toks = WORD.findall(_flat(text))
        low = [w.lower() for w in toks]
        i, count = 0, 0
        while i < len(toks):
            tool = next((len(w) for w in self._tools.get(toks[i], ()) if tuple(toks[i:i + len(w)]) == w), 0)
            if tool:
                i += tool
                continue
            hit = next((k for k in range(min(self._longest, len(toks) - i), 0, -1)
                        if " ".join(low[i:i + k]) in self._said), 0)
            if hit and (toks[i][:1].isupper() or toks[i][:1].isdigit()):
                count += 1
            i += hit or 1
        return count

    def keep(self, rows, name="company", tokens="tokens"):
        """(rows not on the list, how many were left out)."""
        kept = [r for r in rows if not self.matches(r.get(name, ""), (r.get(tokens) or "").replace(";", " ").split())]
        return kept, len(rows) - len(kept)


def city_names(path=None):
    """The places the postings use (config/cities.csv). A city is never a company mention, even when a company shares
    its name."""
    path = Path(path or HERE.joinpath("config", "cities.csv"))
    if not path.exists():
        return []
    import csv
    with open(path, newline="", encoding="utf-8") as f:
        return [r["city"] for r in csv.DictReader(f) if r.get("city")]


def load(path=None, tools_path=None, sources_path=None, also=()):
    """The list, or an empty one marked absent when the file isn't there (a clean clone of the public repo). Tools and
    the job board providers named in config/sources.txt are set aside in text, never as accounts. The export passes the
    model makers named in config/models.json as also, since the code that calls their APIs names them, and the read
    never does, so a rebuilt snapshot stays the same."""
    path = Path(path or DEFAULT)
    tools = (read_names(tools_path or TOOLS) + read_names(sources_path or SOURCES) + read_names(VENDORS)
             + read_names(PLACES) + city_names())
    return Exclusions(read_names(path), tools=tools + list(also), present=path.exists())


def scan(paths, ex=None):
    """A line per file that names an excluded company, with a count and never the name."""
    ex = load() if ex is None else ex
    problems = []
    for p in paths:
        p = Path(p)
        if p.exists():
            n = ex.mentions(p.read_text(encoding="utf-8", errors="ignore"))
            if n:
                problems.append(f"{p.name} names a company on the private exclusion list {n} time(s)")
    return problems
