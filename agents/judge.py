"""The second read: two models check each scored brief against the full text of the postings it rests on, part by
part, so no model passes its own work alone. Since 11/20 they're Claude Opus 5.5 and Claude Sonnet 5.5.

A judge gets prompts/judge.md as its system prompt and one user message: the exact message the brief was written from
(rebuilt from the frozen snapshot, and refused unless it matches the brief's input hash), the full text of every
posting behind its sources, and the brief's claim-bearing parts (why_now as W1 to W3, the likely priority as P, the
first touch as E). The full text is cleaned line by line before any model reads it: invisible characters out, names,
emails, phone numbers and links redacted, and every sentence dropped that names a company on the exclusion list, holds
a never or foreign word, reads like a message to a model, or still trips the privacy scan. The judge returns a verdict
and a one-sentence reason for each part. A brief's verdict is its worst part's, and a brief holds up when both judges
say so.

Planted errors test the judges themselves. Each of the routed model's dev briefs is judged as written and twice more
with one error planted (a date moved, or a claim no posting makes added to the likely priority), and the read reports
how many planted errors each judge caught.
"""
import hashlib
import re
from datetime import date, timedelta
from pathlib import Path

from agents import validate
from app import never
from engine import boards, privacy, redact, textsafety

HERE = Path(__file__).resolve().parent.parent
PROMPT = HERE.joinpath("prompts", "judge.md")
RAW = HERE.joinpath("data", "raw")
VERDICTS = ("holds up", "overreaches", "wrong")
SENTENCE = re.compile(r"(?<=[.!?])\s+")
MARKS = re.compile(r"(?:\s*\[\d+\])+\s*\.?\s*$")
ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
PLANTED_CLAIM = "It also plans to double its sales team by March"
WITHHELD = "(The reason was withheld because it tripped a scan.)"


def prompt_text():
    return PROMPT.read_text(encoding="utf-8")


def prompt_hash():
    return hashlib.sha256(prompt_text().encode()).hexdigest()[:16]


class Cleaner:
    """A posting's full text as a judge may read it, and a check on what a judge writes back."""

    def __init__(self, ex, never_words=None, foreign_words=None, red=None):
        self.ex, self.red, self.dropped, self.done = ex, red or redact.Redactor(), 0, {}
        self.blocked = [p for p in (never.pattern(never.words() if never_words is None else never_words),
                                    never.pattern(never.foreign() if foreign_words is None else foreign_words)) if p]

    def flagged(self, text, keep=()):
        return bool(self.ex.mentions(text) or textsafety.suspicious(text) or any(p.search(text) for p in self.blocked)
                    or privacy.findings(text, keep=keep, redactor=self.red))

    def __call__(self, text, company):
        if (text, company) not in self.done:
            self.done[(text, company)] = self._clean(text, company)
        return self.done[(text, company)]

    def _clean(self, text, company):
        lines = []
        for line in (text or "").splitlines():
            line = textsafety.clean(line).strip()
            if not line:
                continue
            line = self.red.redact(line, [company])[0]
            kept = [s for s in SENTENCE.split(line) if s.strip()]
            safe = [s for s in kept if not self.flagged(s, [company])]
            self.dropped += len(kept) - len(safe)
            if safe:
                lines.append(" ".join(safe))
        return "\n".join(lines)

    def reason(self, text, company):
        return WITHHELD if self.flagged(text, [company]) else text


def postings_for(rec, raw=None):
    """{posting_id: parsed posting} for the postings behind a record's sources, read from the boards as fetched."""
    wanted = {}
    for v in rec["sources"].values():
        if v.get("posting_id"):
            provider, token, _ = v["posting_id"].split(":", 2)
            wanted.setdefault((provider, token), set()).add(v["posting_id"])
    out = {}
    for (provider, token), ids in sorted(wanted.items()):
        path = Path(raw or RAW).joinpath("boards", f"{provider}_{token}.json")
        if path.exists():
            for p in boards.parse(provider, token, path.read_bytes()):
                if p["id"] in ids:
                    out[p["id"]] = p
    return out


def parts_of(brief):
    """[(id, text)] for the parts a judge reads, in order: W1 to W3, P and E."""
    out = [(f"W{i}", (s or {}).get("text", "")) for i, s in enumerate(brief.get("why_now") or [], 1)]
    out.append(("P", (brief.get("priority") or {}).get("text", "")))
    t = brief.get("first_touch") or {}
    cites = "".join(f"[{c}]" for c in t.get("cites") or []) or "no source"
    out.append(("E", f"Subject: {t.get('subject', '')}\n{t.get('body', '')}\nThe email rests on {cites}."))
    return out


def message(brief_message, rec, brief, posts, clean):
    """(the judge's user message, the part ids in order) for one brief."""
    nums = {}
    for n, v in sorted(rec["sources"].items(), key=lambda kv: int(kv[0])):
        if v.get("posting_id"):
            nums.setdefault(v["posting_id"], []).append(n)
    blocks = []
    for pid, ns in nums.items():
        label = "".join(f"[{n}]" for n in ns)
        title = rec["sources"][ns[0]]["title"]
        if pid in posts:
            blocks.append(f'The posting behind {label}, "{title}":\n{clean(posts[pid]["text"], rec["account"])}')
        else:
            blocks.append(f'The posting behind {label}, "{title}": its full text wasn\'t found, so judge by its source.')
    parts = parts_of(brief)
    text = ("The brief was written from this message:\n\n" + brief_message.strip() + "\n\nThe full text of each "
            "posting:\n\n" + "\n\n".join(blocks) + "\n\nThe brief's parts:\n\n"
            + "\n\n".join(f"{i}: {t}" for i, t in parts) + "\n")
    return text, [i for i, _ in parts]


def input_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def check(text, ids):
    """(parts as {id: {verdict, reason}} or None, errors) for a judge's reply."""
    obj = validate.first_object(text)
    if not isinstance(obj, dict) or not isinstance(obj.get("parts"), list):
        return None, ["the reply isn't one JSON object with a parts list"]
    got, errors = {}, []
    for p in obj["parts"]:
        pid = p.get("id") if isinstance(p, dict) else None
        if pid not in ids:
            errors.append(f"an unknown part: {pid}")
        elif p.get("verdict") not in VERDICTS:
            errors.append(f"{pid}: the verdict must be holds up, overreaches or wrong")
        elif not isinstance(p.get("reason"), str) or not p["reason"].strip():
            errors.append(f"{pid}: no reason given")
        else:
            got[pid] = {"verdict": p["verdict"], "reason": " ".join(p["reason"].split())[:400]}
    missing = [i for i in ids if i not in got]
    if missing:
        errors.append("missing parts: " + ", ".join(missing))
    return (None if errors else got), errors


def worst(parts):
    return max((p["verdict"] for p in parts.values()), key=VERDICTS.index)


def repair_message(user, reply, errors):
    return (user + "\nYour previous reply:\n" + (reply or "").strip() + "\n\nIt had these problems:\n"
            + "\n".join(f"- {e}" for e in errors) + "\n\nReturn only the corrected JSON object.\n")


def _shift(day, sources, read_on):
    """A date nine days off, or thirteen, that no source holds and that isn't after the read date."""
    taken = {v.get("posted") for v in sources.values()}
    for d in (-9, -13, 9, 13):
        new = (date.fromisoformat(day) + timedelta(days=d)).isoformat()
        if new not in taken and new <= read_on:
            return new
    return None


def plant(brief, sources, read_on):
    """[(kind, part id, brief with one error planted)]: a why-now date moved, and a claim no posting makes added to
    the likely priority. Each is a fresh copy, and the original is left alone."""
    import copy
    out = []
    for i, s in enumerate(brief.get("why_now") or [], 1):
        text = re.sub(r"[\"“][^\"”]*[\"”]", lambda m: " " * len(m.group(0)), s.get("text", ""))
        m = ISO.search(text)
        new = m and _shift(m.group(1), sources, read_on)
        if new:
            b = copy.deepcopy(brief)
            b["why_now"][i - 1]["text"] = s["text"][:m.start(1)] + new + s["text"][m.end(1):]
            out.append(("a date moved", f"W{i}", b))
            break
    p = (brief.get("priority") or {}).get("text", "")
    marks = re.findall(r"\[\d+\]", p)
    if p and marks:
        b = copy.deepcopy(brief)
        b["priority"]["text"] = p.rstrip() + f" {PLANTED_CLAIM} {marks[0]}."
        out.append(("a claim added", "P", b))
    return out


def summarize(judged, judges, route, planted=()):
    """The read's numbers, with the gate: at least nine in ten of the routed model's briefs hold up with both judges,
    and it counts only when the pair caught at least nine in ten of the planted errors.

    judged: [{account, model, judge, verdict}] for the scored briefs. planted: [{account, kind, part, judge, parts}]
    for the planted errors, and [{..., kind: "as written"}] for the briefs they were planted in."""
    by_brief = {}
    for j in judged:
        by_brief.setdefault((j["account"], j["model"]), {})[j["judge"]] = j["verdict"]
    models = {}
    for (account, model), verdicts in sorted(by_brief.items()):
        m = models.setdefault(model, {"briefs": 0, "judged_by_both": 0, "both_hold": 0, "one_holds": 0,
                                      "neither_holds": 0})
        m["briefs"] += 1
        if not all(j in verdicts for j in judges):
            continue
        m["judged_by_both"] += 1
        holds = sum(1 for j in judges if verdicts[j] == "holds up")
        m["both_hold" if holds == len(judges) else "one_holds" if holds else "neither_holds"] += 1
    per_judge = {j: {v: sum(1 for x in judged if x["judge"] == j and x["verdict"] == v) for v in VERDICTS}
                 for j in judges}
    both = [v for v in by_brief.values() if all(j in v for j in judges)]
    agree = sum(1 for v in both if len({v[j] == "holds up" for j in judges}) == 1)
    r = models.get(route, {"briefs": 0, "judged_by_both": 0, "both_hold": 0})
    caught = {j: {"caught": 0, "of": 0} for j in judges}
    gate_caught, gate_of, controls = 0, 0, {j: {"holds up": 0, "of": 0} for j in judges}
    plants = {}
    for x in planted:
        if x["kind"] == "as written":
            controls[x["judge"]]["of"] += 1
            controls[x["judge"]]["holds up"] += x["verdict"] == "holds up"
            continue
        hit = x["parts"][x["part"]]["verdict"] != "holds up"
        caught[x["judge"]]["of"] += 1
        caught[x["judge"]]["caught"] += hit
        plants.setdefault((x["account"], x["kind"]), {})[x["judge"]] = hit
    for hits in plants.values():
        if all(j in hits for j in judges):
            gate_of += 1
            gate_caught += any(hits.values())
    need, planted_need = -(-9 * r["briefs"] // 10), -(-9 * gate_of // 10)  # nine in ten, rounded up
    complete = r["judged_by_both"] == r["briefs"] > 0
    trusted = gate_of > 0 and gate_caught >= planted_need
    gate = {"model": route, "held": r["both_hold"], "of": r["briefs"], "need": need, "complete": complete,
            "planted_caught": gate_caught, "planted_of": gate_of, "planted_need": planted_need, "trusted": trusted,
            "passes": complete and trusted and r["both_hold"] >= need}
    return {"judges": list(judges), "route": route, "by_model": models, "by_judge": per_judge,
            "agreement": {"briefs": len(both), "agree": agree},
            "planted": {"by_judge": caught, "by_the_gate": {"caught": gate_caught, "of": gate_of},
                        "as_written_holds_up": controls},
            "gate": gate}
