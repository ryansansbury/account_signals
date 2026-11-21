"""What a model sees for one account: the numbered sources as one user message, and the hashes the recorder keys on.

The sources come from the account's own signals only, strongest first: the intent signals that count toward its score,
then up to three tools it names as its stack, then up to three of its go-to-market postings not already there, twelve
at most, plus source [0] for its board. Two signals from one posting are marked as the same posting, so a model counts
postings and not sources. Nothing else about the company reaches a model. An excluded company never gets here, and the
recorder refuses one before it builds a message.
"""
import hashlib
from pathlib import Path

from engine import claims

HERE = Path(__file__).resolve().parent.parent
PROMPT = HERE.joinpath("prompts", "brief.md")
MAX_SIGNALS = 12
KIND = {"published": "published", "created": "created", "updated": "last updated"}


def prompt_text():
    return PROMPT.read_text(encoding="utf-8")


def prompt_hash():
    return hashlib.sha256(prompt_text().encode()).hexdigest()[:16]


def pick(account, signals):
    """The account's signals in the order the brief sees them: counted intent first, then stack, then pace."""
    by_id = {s["sid"]: s for s in signals}
    counted = [by_id[r["sid"]] for r in sorted(account["intent_rows"], key=lambda r: (-r["points"], r["sid"]))
               if r["family"] != "pace" and r["sid"] in by_id]
    stack = sorted((s for s in signals if s["family"] == "stack"), key=lambda s: (s["strength"] != "uses", s["sid"]))[:3]
    out = []
    for s in counted + stack:
        if s not in out:
            out.append(s)
    # A pace signal adds only its label, so one whose posting is already here would read as a second posting.
    seen = {s["posting_id"] for s in out}
    pace = [by_id[r["sid"]] for r in account["intent_rows"] if r["family"] == "pace" and r["sid"] in by_id
            and by_id[r["sid"]]["posting_id"] not in seen][:3]
    return (out + pace)[:MAX_SIGNALS]


def eligible(account):
    """An account gets a brief when at least two intent signals other than hiring pace count toward its score."""
    return sum(1 for r in account["intent_rows"] if r["family"] != "pace") >= 2


def board_of(account):
    known = account["us"] + account["nonus"]
    hub = f"{account['hub']['city']}, {account['hub']['state']}" if account.get("hub") else ""
    return {"openings": account["openings"], "read_on": account["read_on"], "hub": hub,
            "us_pct": round(100 * account["us"] / known) if known else None}


def message(account, chosen, labels):
    """The user message: the account, the read date and the numbered sources."""
    sources = claims.sources_for(account["account"], board_of(account), chosen)
    lines = [f"Account: {account['account']}", f"Read date: {account['read_on']}", "", f"[0] Board. {sources[0]['text']}"]
    first = {}
    for n, s in enumerate(chosen, 1):
        when = f"{KIND.get(s['date_kind'], 'posted')} {s['posted']}" if s["posted"] else "date not given"
        if s["posting_id"] in first:  # two signals from one posting, so a count of postings counts it once
            when += f" (same posting as [{first[s['posting_id']]}])"
        first.setdefault(s["posting_id"], n)
        line = f'[{n}] Posting "{s["title"]}", {when}. Signal: {labels[s["family"]]}'
        if s["family"] == "stack":
            line += f" ({s['tool']})"
        if s["excerpt"] != s["title"]:
            line += f'. Quote: "{s["excerpt"]}"'
        lines.append(line)
    return "\n".join(lines) + "\n", sources


def input_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]
