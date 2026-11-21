"""Take people's details out of posting text before anything stores it.

Every posting's text, title and department passes through redact() before a signal is found or an excerpt is cut, in
four layers:
1. Patterns: email addresses, phone numbers, links with a scheme, a "www." or a path, social handles, and LinkedIn
   recruiter tags (#LI- codes, which carry a recruiter's initials). A bare company domain such as a tool's name stays.
2. Cues: a capitalized name of one to three words after "contact," "reach out to," "recruiter," "hiring manager,"
   "reports to," "led by," "work closely with" and the like, or after a leader's title and a comma ("our CRO, ...").
3. Likely names: a capitalized pair or triple whose first word is a common first name (config/first_names.txt) or
   whose last word is a common surname (config/surnames.txt).
4. engine/privacy.py scans everything that ships for anything that slipped through, and the build stops on a hit.

A run of words is never a person when any word in it is a business, role or place word, a tool from config/tools.txt,
part of the account's own name, or when the run names a place in the Census Bureau's Gazetteer. Each removal is marked
where it was ("[name removed]") and counted. Over-removal is accepted, since a lost word costs less than a kept name.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CONFIG = HERE.joinpath("config")

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w.])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\w])"
                   r"|(?<![\w.])\+\d{1,3}(?:[\s.-]?\d{2,4}){2,5}(?![\w])")
LINK = re.compile(r"\b(?:https?://|www\.)[^\s<>\"')\]]+"
                  r"|\b[\w-]+(?:\.[\w-]+)*\.(?:com|io|ai|co|net|org|us|app|dev|example|me)/[^\s<>\"')\]]*", re.I)
HANDLE = re.compile(r"(?<![\w.@/])@[A-Za-z0-9_]{2,30}\b")
LI_TAG = re.compile(r"\s*#LI-[A-Za-z0-9]+\b", re.I)
WORD = r"\b[A-Z][a-z]+(?:['’-][A-Za-z]+)*(?![A-Za-z])"
RUN = re.compile(rf"{WORD}(?:(?:\s+[A-Z]\.)?\s+{WORD})+")
TOKEN = re.compile(rf"{WORD}|\b[A-Z]\.")
CUE = re.compile(r"\b(?i:contact(?:ing)?|reach(?:ing)? out to|e-?mail|recruiter(?:\s+is)?|recruiting partner|"
                 r"talent (?:acquisition )?partner|hiring manager(?:\s+is)?|reports? (?:directly )?to|reporting "
                 r"(?:directly )?to|led by|managed by|work(?:ing)? (?:closely |directly )?(?:with|alongside)|"
                 r"founded by|posted by|ask for)\s*[:,]?\s+(?i:our\s+|your\s+)?"
                 rf"({WORD}(?:\s+[A-Z]\.)?(?:\s+{WORD}){{0,2}})")
TITLE_COMMA = re.compile(r"\b(?:CEO|CRO|CFO|COO|CTO|CMO|CPO|CIO|CHRO|(?i:founder|co-?founder|president|"
                         r"chief [a-z]+ officer|(?:svp|evp|vp|vice president|head|director|manager|leader)"
                         r"(?: of)?(?: [a-z&]+){0,4}))"
                         rf",\s+({WORD}(?:\s+[A-Z]\.)?(?:\s+{WORD}){{0,2}})")
TAGS = {"name": "[name removed]", "email": "[email removed]", "phone": "[phone removed]", "link": "[link removed]",
        "handle": "[handle removed]"}
VOCAB = set("""
sales marketing operations operation ops revenue revops finance financial product products engineering engineer
engineers customer customers success support team teams leadership leader leaders executive executives manager
managers management director directors head vice president chief officer analyst analysts account accounts business
development data analytics people talent legal security partner partners partnerships channel enterprise mid market
commercial strategy strategic systems system enablement growth demand field inside solutions solution services service
professional global national regional region territory territories north south east west central northeast northwest
southeast southwest midwest america american americas united states us usa new york city county lake beach springs
falls valley park heights island islands bay coast harbor grand upper lower greater metro downtown fort port mount
mountain saint san santa los las el la del de st point river hills village township district area office offices
hq headquarters campus remote hybrid onsite program project projects platform platforms cloud crm erp cpq software
saas hardware health healthcare care clinical medical energy solar power logistics freight supply chain manufacturing
consumer retail brand brands group holdings company companies corp inc llc labs lab tech technologies technology the
our your their this that these those we you they and or of for with in on at to by from about across monday tuesday
wednesday thursday friday saturday sunday january february march april may june july august september october
november december series fortune founding senior junior principal staff lead associate specialist coordinator
administrator admin architect consultant representative rep development developer intern internship full time part
contract benefits equal opportunity employer diversity inclusion mission vision values culture about role
responsibilities requirements qualifications preferred required bonus compensation salary equity medical dental
vision pto holiday holidays insurance plan plans day days week weeks month months year years quarter quarterly
annual high low first second third world class best great
""".split())


def _words(path):
    if not Path(path).exists():
        return set()
    out = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            out.update(line.split())
    return out


def _tool_words(path):
    out = set()
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                out.update(w.lower() for w in re.findall(r"[A-Za-z0-9]+", line))
    return out


class Redactor:
    def __init__(self, first=None, last=None, tools=None, places=()):
        self.first = _words(first or CONFIG.joinpath("first_names.txt"))
        self.last = _words(last or CONFIG.joinpath("surnames.txt"))
        self.vocab = VOCAB | _tool_words(tools or CONFIG.joinpath("tools.txt"))
        if not places and CONFIG.joinpath("name_places.txt").exists():
            places = [ln.strip() for ln in CONFIG.joinpath("name_places.txt").read_text(encoding="utf-8").splitlines()
                      if ln.strip() and not ln.startswith("#")]
        self.places = {p.lower() for p in places}

    def _not_a_person(self, words, keep):
        low = [w.lower().replace("’", "'") for w in words]
        if any(w in self.vocab or w in keep for w in low):
            return True
        return " ".join(low) in self.places

    def likely(self, words, keep=frozenset()):
        """A run of capitalized words reads as a person's name."""
        if len(words) < 2 or self._not_a_person(words, keep):
            return False
        return words[0] in self.first or words[-1] in self.last

    def names_in_run(self, text, keep=frozenset()):
        """A run of capitalized words with every adjacent pair that reads as a name replaced, so "Revenue Operations
        Manager Jane Q. Smith" keeps its title and loses the name."""
        toks = [(t.start(), t.end(), t.group(0)) for t in TOKEN.finditer(text)]
        words = [i for i, t in enumerate(toks) if not t[2].endswith(".")]
        place = set()  # words inside a longer run that names a Gazetteer place, such as San Luis Obispo
        for size in range(len(words), 1, -1):
            for s in range(len(words) - size + 1):
                span = words[s:s + size]
                if " ".join(toks[i][2] for i in span).lower() in self.places:
                    place.update(span)
        marked = set()
        for a, b in zip(words, words[1:]):
            if a in place and b in place:
                continue
            if self.likely([toks[a][2], toks[b][2]], keep):
                marked.update(range(a, b + 1))
        if not marked:
            return text, 0
        groups = []
        for k in sorted(marked):
            if groups and k == groups[-1][-1] + 1:
                groups[-1].append(k)
            else:
                groups.append([k])
        out, pos = [], 0
        for g in groups:
            out += [text[pos:toks[g[0]][0]], TAGS["name"]]
            pos = toks[g[-1]][1]
        out.append(text[pos:])
        return "".join(out), len(groups)

    def redact(self, text, keep=()):
        """(text without people's details, {kind: count})."""
        counts = dict.fromkeys(TAGS, 0)
        counts["tag"] = 0
        keep = {w.lower() for k in keep for w in re.findall(r"[A-Za-z0-9']+", k or "")}
        if not text:
            return text or "", counts

        def sub(kind, pattern, s):
            def fn(_m):
                counts[kind] += 1
                return TAGS[kind]
            return pattern.sub(fn, s)

        def drop_tag(_m):
            counts["tag"] += 1
            return ""

        s = LI_TAG.sub(drop_tag, text)
        s = sub("email", EMAIL, s)
        s = sub("link", LINK, s)
        s = sub("handle", HANDLE, s)
        s = sub("phone", PHONE, s)

        def cue(m):
            name = m.group(1)
            words = [w for w in name.split() if not re.match(r"^[A-Z]\.$", w)]
            # Keep only the leading words that could be a name, so "Jane Doe and Sales" stops at "Doe".
            if self._not_a_person(words[:1], keep):
                return m.group(0)
            if len(words) == 1 and words[0] not in self.first:
                return m.group(0)
            if len(words) > 1 and self._not_a_person(words, keep):
                return m.group(0)
            counts["name"] += 1
            return m.group(0)[:m.start(1) - m.start(0)] + TAGS["name"]

        s = CUE.sub(cue, s)
        s = TITLE_COMMA.sub(cue, s)

        def run(m):
            text_, n = self.names_in_run(m.group(0), keep)
            counts["name"] += n
            return text_

        s = RUN.sub(run, s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        return s, counts


_DEFAULT = {}


def redact(text, keep=(), places=()):
    """redact() with the build's own lists, loaded once."""
    key = id(places) if places else 0
    if key not in _DEFAULT:
        _DEFAULT[key] = Redactor(places=places)
    return _DEFAULT[key].redact(text, keep)
