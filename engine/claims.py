"""Check a brief and its first touch against the sources they cite. A claim that the sources don't hold is flagged.

The sources are numbered: [0] is the account's board (its open roles, hub city and US share on the read date) and [1]
onward are its signals, each a dated posting with a quoted sentence. Each sentence of the brief carries [n] markers, and
the first touch lists the sources it rests on. For each sentence the checker finds:
- citations: every [n] is a real source, and every sentence of why_now and the priority cites at least one;
- numbers: each number is in a cited source, counts no more postings than it cites ("three revenue operations roles"),
  or is the year of the read date or of a cited posting, and a number word that counts nothing ("one of them") is
  left alone;
- dates written as 2026-10-30: each is a cited posting's date or appears in a cited source;
- dates and recency: "4 days ago" (or "days old," or "days before the read date"), "in the last 30 days" (or "in the
  10 days before the read date"), "this month," "since October," "in July" and "November 2" must agree with the cited
  postings' dates against the read date (in the first touch, whose cites serve the whole email, one cited posting
  inside a window is enough), while a phrase inside quotation marks belongs to the quote;
- quotes: text in quotation marks appears word for word in a cited source;
- names: a capitalized word after a sentence's first word that isn't in a cited source, the account's name or the
  shared vocabulary is flagged, which keeps out people's names and invented products (a hyphenated word such as
  "CRM-related" by its capitalized parts, and a sentence can start after a full stop inside one item);
- tools: a tool from config/tools.txt appears in a cited source;
- promises, in the first touch: guarantees, savings, free offers, ROI and percentages tied to a result;
- the rules: the shape of each field, 120 words in the first touch, both placeholders, and no redaction marker copied.
It doesn't judge tone or paraphrase, and the page says so. site/claims.js repeats every rule for the live edit, and
tests/vectors/claims.json holds the cases both must agree on.
"""
import re
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
             "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
             "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]
MON = {m[:3]: i + 1 for i, m in enumerate(MONTHS)}
UNITS = {"day": 1, "days": 1, "week": 7, "weeks": 7, "month": 30, "months": 30, "quarter": 91, "quarters": 91}
COUNTED = r"(?:roles?|postings?|openings?|positions?|jobs?|hires?|reqs?|listings?)"
MARK = re.compile(r"\s*\[(\d+)\]")
ISO = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
QUOTE = re.compile(r"[\"“]([^\"”]{3,})[\"”]")
READ = r"before\s+(?:the\s+|that\s+)?(?:read\s+date|board\s+was\s+read)"
AGO = re.compile(r"(?<![Tt]he )\b(\d+|" + "|".join(NUM_WORDS) + r")\s+days?\s+(?:ago|old|" + READ + r")\b", re.I)
WINDOW = re.compile(r"\b(?:in|over|within|during) the (?:(?:last|past) (?:(\d+|" + "|".join(NUM_WORDS) +
                    r"|a|one)\s+)?(days?|weeks?|months?|quarters?)|(\d+|" + "|".join(NUM_WORDS) +
                    r")\s+(days?|weeks?)\s+" + READ + r")\b", re.I)
THIS = re.compile(r"\bthis (week|month|quarter)\b", re.I)
SINCE = re.compile(r"\bsince (" + "|".join(MONTHS) + r")\b", re.I)
MONTH_DAY = re.compile(r"\b(" + "|".join(m[:3] for m in MONTHS) + r")[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b", re.I)
IN_MONTH = re.compile(r"\b(?:in|from|during) (" + "|".join(m.capitalize() for m in MONTHS) + r")\b(?!\s+\d{1,2}\b)")
NUMBER = re.compile(r"\$?\d[\d,]*(?:\.\d+)?(?:[%kKmM]\b|%)?|\b(?:" + "|".join(NUM_WORDS) + r")\b|\ba dozen\b", re.I)
CAP = re.compile(r"\b[A-Z][A-Za-z'’&.-]*[A-Za-z]|\b[A-Z]\b")
PROMISES = [re.compile(p, re.I) for p in (
    r"\bguarantee\w*", r"\bsave (?:you|your team)\b", r"\bincrease (?:your )?(?:revenue|pipeline|win rates?|bookings)\b",
    r"\bdouble (?:your )?\w+", r"\b\d+\s*(?:%|percent)\s+(?:more|faster|less|lift|increase|improvement|growth)\b",
    r"\bfree\b", r"\bno cost\b", r"\bROI\b", r"\bwe(?:'ll| will) (?:deliver|get you|make sure|guarantee)\b")]
SHARED = set("""
I I'd I'm I'll I've A An The This That These Those It It's Its We We're Our You You're Your They Their If When Since
With For From In On At As And But Or So Hi Hello Thanks Thank Best Would Could Can Is Are Was Were Do Does Did Has Have
Had Will What Why How Who Where Which Happy Glad Curious Saw Noticed Reading Worth Quick Open Glad One Two Three
Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August September
October November December US U.S. USA CRM CRO VP SVP EVP CFO COO CEO GTM SaaS ERP CPQ AI ML BI KPI KPIs QBR QBRs SDR
SDRs BDR BDRs AE AEs RevOps Ops Sales Revenue Operations Operation Marketing Finance Customer Success Analytics Data
Engineering Engineer Manager Director Head Lead Leader Analyst Analysts Administrator Admin Systems Strategy Enablement
Deal Desk Partnerships Leadership Team Teams Pipeline Forecast Forecasting Territory Territories Region Regions West East
North South Midwest Southeast Northeast Southwest Northwest Mountain Central Coast Pacific Atlantic America Americas
Enterprise Mid-Market Commercial SMB Senior Principal Staff Associate Specialist Coordinator Vice President Chief Officer
""".split())
TOOLS_FILE = HERE.joinpath("config", "tools.txt")


def load_tools(path=None):
    p = Path(path or TOOLS_FILE)
    return sorted((ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()
                   and not ln.startswith("#")), key=len, reverse=True)


_FIRST = {}


def load_first_names(path=None):
    """The first-name list redaction uses, so a sentence that opens with a person's first name is still caught."""
    key = str(path or "")
    if key not in _FIRST:
        p = Path(path or HERE.joinpath("config", "first_names.txt"))
        _FIRST[key] = {w for ln in p.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")
                       for w in ln.split()}
    return _FIRST[key]


def numval(tok):
    """A number token as a float: '3', '1,200', '92%', '$150K', 'three', 'a dozen'."""
    t = tok.lower().replace(",", "").replace("$", "").strip()
    if t == "a dozen":
        return 12.0
    if t in NUM_WORDS:
        return float(NUM_WORDS[t])
    mult = 1.0
    if t.endswith("%"):
        t = t[:-1]
    elif t.endswith("k"):
        t, mult = t[:-1], 1000.0
    elif t.endswith("m"):
        t, mult = t[:-1], 1000000.0
    try:
        return float(t) * mult
    except ValueError:
        return None


def days_between(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def source_text(src):
    return " ".join(str(src.get(k) or "") for k in ("title", "excerpt", "text"))


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"“(\[{])", text or "") if s.strip()]


def tool_in(tool, text):
    return re.search(r"(?<![\w-])" + re.escape(tool) + r"(?![\w-])", text) is not None


def count_of(tok):
    v = numval(tok) if tok and tok.lower() not in ("a", "one") else 1.0
    return int(v)


def check_sentence(text, cites, sources, account, read_on, tools, need_cite=True, promises=False, first_names=None,
                   pooled=False):
    """Problems with one sentence, as 'kind: detail' strings in a fixed order. Pooled is the first touch, whose cites
    serve the whole email, so a recency phrase needs one cited posting inside it where a brief sentence needs all."""
    problems = []
    plain = MARK.sub("", text).strip()
    for c in cites:
        if c not in sources:
            problems.append(f"cite: [{c}]")
    cited = [sources[c] for c in cites if c in sources]
    if need_cite and not cited:
        problems.append("cite: none")
    src = " ".join(source_text(s) for s in cited)
    src_low = " ".join(src.lower().split())
    posts = [s for s in cited if s.get("posted")]
    for q in QUOTE.findall(plain):
        core = q.strip().strip("…").rstrip(".,;:!?").strip()  # American style puts a closing period inside the quote
        if " ".join(core.lower().split()) not in src_low:
            problems.append(f'quote: "{q}"')
    bare = QUOTE.sub(" ", plain)
    skip = []
    for m in ISO.finditer(bare):
        skip.append(m.span())
        if not any(s["posted"] == m.group(0) for s in posts) and m.group(0) not in src:
            problems.append(f"date: {m.group(0)}")
    for m in AGO.finditer(bare):
        skip.append(m.span())
        if not any(days_between(s["posted"], read_on) == count_of(m.group(1)) for s in posts):
            problems.append(f"recency: {m.group(0)}")
    ages = sorted(days_between(s["posted"], read_on) for s in posts)
    for m in WINDOW.finditer(bare):
        skip.append(m.span())
        n, unit = (m.group(3), m.group(4)) if m.group(4) else (m.group(1), m.group(2))
        limit = count_of(n) * UNITS[unit.lower()]
        if not ages or (ages[0] if pooled else ages[-1]) > limit:
            problems.append(f"recency: {m.group(0)}")
    for m in THIS.finditer(bare):
        skip.append(m.span())
        limit = UNITS[m.group(1).lower()]
        if not ages or (ages[0] if pooled else ages[-1]) > limit:
            problems.append(f"recency: {m.group(0)}")
    dates = sorted(s["posted"] for s in posts)
    for m in SINCE.finditer(bare):
        skip.append(m.span())
        month = MONTHS.index(m.group(1).lower()) + 1
        year = int(read_on[:4]) - (1 if month > int(read_on[5:7]) else 0)
        start = f"{year}-{month:02d}-01"
        if not dates or (dates[-1] if pooled else dates[0]) < start:
            problems.append(f"date: {m.group(0)}")
    for m in IN_MONTH.finditer(bare):  # "in July": a cited posting went up that month, in the year before the read
        skip.append(m.span())
        month = MONTHS.index(m.group(1).lower()) + 1
        year = int(read_on[:4]) - (1 if month > int(read_on[5:7]) else 0)
        if not any(d[:7] == f"{year}-{month:02d}" for d in dates):
            problems.append(f"date: {m.group(0)}")
    src_days = {(int(d[5:7]), int(d[8:10])) for d in ISO.findall(src)}  # the read date, when [0] is cited
    for m in MONTH_DAY.finditer(bare):
        skip.append(m.span())
        want = (MON[m.group(1).lower()[:3]], int(m.group(2)))
        if not any((int(s["posted"][5:7]), int(s["posted"][8:10])) == want for s in posts) and want not in src_days:
            problems.append(f"date: {m.group(0)}")
    no_dates = re.sub(r"\d{4}-\d{2}-\d{2}", " ", src)
    have = {numval(t) for t in NUMBER.findall(no_dates)} | {numval(t) for t in NUMBER.findall(account)}
    years = {float(read_on[:4])} | {float(s["posted"][:4]) for s in posts}
    distinct = len({s["posting_id"] for s in cited if s.get("posting_id")})
    for m in NUMBER.finditer(bare):
        if any(a <= m.start() < b for a, b in skip):
            continue
        v = numval(m.group(0))
        if v is None or v in have or v in years:
            continue
        counts = re.match(r"\s+(?:[a-z-]+\s+){0,4}" + COUNTED + r"\b", bare[m.end():m.end() + 40], re.I)
        if m.group(0)[0].isalpha() and not counts:  # a number word that counts nothing ("one of them") isn't a claim
            continue
        if counts and 1 <= v <= distinct:  # a count of postings may not exceed the distinct postings it cites
            continue
        problems.append(f"number: {m.group(0)}")
    # A sentence starts at the front and after any full stop inside the text, since one item can hold two sentences.
    starts = {len(bare) - len(bare.lstrip())} | {m.end() for m in re.finditer(r"[.!?]\s+", bare)}
    acct_words = set(re.findall(r"[A-Za-z0-9'’&.-]+", account))
    named_tools = [t for t in tools if tool_in(t, plain)]
    first_names = load_first_names() if first_names is None else first_names

    def known(w):
        return (w in SHARED or w in acct_words or any(w in t.split() for t in named_tools)
                or re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", src) is not None)
    for m in CAP.finditer(bare):
        w = re.sub(r"['’]s$", "", m.group(0).rstrip("."))
        if known(w) or ("-" in w and all(known(p) for p in w.split("-") if re.match(r"[A-Z]", p))):
            continue  # "CRM-related" is checked by its capitalized parts
        if m.start() in starts and w not in first_names:
            continue
        problems.append(f"name: {w}")
    for t in named_tools:
        if not tool_in(t, src):
            problems.append(f"tool: {t}")
    if promises:
        for p in PROMISES:
            m = p.search(plain)
            if m:
                problems.append(f"promise: {m.group(0)}")
    if "removed]" in plain:
        problems.append("rule: a redaction marker")
    return problems


def check_touch(touch, sources, account, read_on, tools, first_names=None):
    """Problems with the first touch: its rules, then each sentence's claims against what it cites."""
    out = []
    body = (touch.get("body") or "").strip()
    cites = [int(c) for c in touch.get("cites") or []]
    if len(touch.get("subject") or "") > 60:
        out.append("rule: subject over 60 characters")
    words = len(re.findall(r"\S+", body))
    if words > 120:
        out.append(f"rule: {words} words")
    if not body.startswith("Hi {first_name},"):
        out.append("rule: greeting")
    if "{sender_name}" not in body:
        out.append("rule: sign-off")
    if re.search(r"\{(?!first_name\}|sender_name\})[^}]*\}", body):
        out.append("rule: an unknown placeholder")
    if MARK.search(body):
        out.append("rule: a citation marker in the email")
    if not cites:
        out.append("cite: none")
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("Hi {first_name}") or "{sender_name}" in line:
            continue
        for s in sentences(line):
            out += check_sentence(s, cites, sources, account, read_on, tools, need_cite=False, promises=True,
                                  first_names=first_names, pooled=True)
    return out


def check_brief(brief, sources, account, read_on, tools=None, lint=None, first_names=None):
    """{sentences: [{field, text, cites, problems}], problems: [...], ok: bool} for one recorded brief."""
    tools = load_tools() if tools is None else tools
    rows, problems = [], []
    why = brief.get("why_now") or []
    if not 2 <= len(why) <= 3:
        problems.append(f"rule: {len(why)} why-now sentences")
    items = [("why_now", s) for s in why] + [("priority", brief.get("priority") or {})]
    for field, item in items:
        text = (item.get("text") or "").strip()
        cites = [int(c) for c in MARK.findall(text)]
        p = check_sentence(text, cites, sources, account, read_on, tools, first_names=first_names)
        if lint:
            p += [f"writing: {x}" for x in lint(MARK.sub("", text))]
        rows.append({"field": field, "text": text, "cites": cites, "problems": p})
    qs = brief.get("questions") or []
    if len(qs) != 3 or not all(q.strip().endswith("?") for q in qs):
        problems.append("rule: three questions")
    unknowns = brief.get("unknowns") or []
    if not 2 <= len(unknowns) <= 4:
        problems.append(f"rule: {len(unknowns)} unknowns")
    for field, text in [("question", q) for q in qs] + [("unknown", u) for u in unknowns]:
        p = []
        if "removed]" in text:
            p.append("rule: a redaction marker")
        if lint:
            p += [f"writing: {x}" for x in lint(text)]
        rows.append({"field": field, "text": text, "cites": [], "problems": p})
    touch = brief.get("first_touch") or {}
    tp = check_touch(touch, sources, account, read_on, tools, first_names)
    if lint:
        for line in (touch.get("body") or "").splitlines():
            if line.strip() and not line.startswith("Hi {first_name}") and "{sender_name}" not in line:
                tp += [f"writing: {x}" for x in lint(line.strip())]
    rows.append({"field": "first_touch", "text": touch.get("body") or "", "cites": touch.get("cites") or [],
                 "problems": tp})
    ok = not problems and not any(r["problems"] for r in rows)
    return {"sentences": rows, "problems": problems, "ok": ok}


def sources_for(account, board, signals):
    """{n: source} for the prompt and the checks: [0] the board, then the signals in the order given. The board's
    sentences follow the writing rules the briefs must keep, since a model copies the shape of its sources."""
    n = board["openings"]
    text = f"{account} had {n} open role{'' if n == 1 else 's'} on its public job board on {board['read_on']}."
    if board.get("hub"):
        text += f" The US city with the most of its open roles was {board['hub']}."
    if board.get("us_pct") is not None:
        text += f" The US held {board['us_pct']}% of the roles that named a place."
    out = {0: {"kind": "board", "text": text, "posted": ""}}
    for i, s in enumerate(signals, 1):
        out[i] = {"kind": "signal", "sid": s["sid"], "title": s["title"], "excerpt": s["excerpt"],
                  "posted": s["posted"], "posting_id": s["posting_id"], "family": s["family"]}
    return out
