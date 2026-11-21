"""A deterministic stand-in for a model, for previews, the dry run and the click-through. It's never a result.

It answers the same call a model does, model(system, user) -> (text, meta), by reading the numbered sources in the user
message and writing a plain brief that passes every check: titles it saw, one quote copied from a source, generic
questions and unknowns, and a first touch about the top posting. Every record it makes is labeled "Stand-in (not a
model)," the scoreboard leaves it out, and the export drops it.
"""
import json
import re

LINE = re.compile(r'^\[(\d+)\] Posting "(.*?)", [^.]*\. Signal: ([^.(]+?)(?: \([^)]*\))?(?:\. Quote: "(.*)")?$')


def model(system, user):
    sources = [(int(m.group(1)), m.group(2), m.group(3).strip(), m.group(4)) for m in
               (LINE.match(ln) for ln in user.splitlines()) if m]
    first = sources[0] if sources else (0, "", "", None)
    n1, title1, label1, _ = first
    why = [{"text": f'Its board shows a "{title1}" posting [{n1}].'}]
    quoted = next(((n, q) for n, _, _, q in sources if q), None)
    if quoted:
        words = quoted[1].lstrip("…").split()[:10]
        why.append({"text": f'One posting says "{" ".join(words).rstrip(",.")}" [{quoted[0]}].'})
    elif len(sources) > 1:
        why.append({"text": f'It also shows a "{sources[1][1]}" posting [{sources[1][0]}].'})
    else:
        why.append({"text": f"The board was read on the date given [0]."})
    brief = {
        "why_now": why,
        "priority": {"text": f"Likely help with the {label1} the postings point to [{n1}]."},
        "questions": ["What is driving the new roles?", "Who owns revenue reporting today?",
                      "What would a good first month look like?"],
        "unknowns": ["Which CRM the team uses", "How large the sales team is"],
        "first_touch": {"subject": "Your revenue operations hiring",
                        "body": f'Hi {{first_name}},\n\nI saw the "{title1}" posting on your job board and wanted to ask '
                                f"how the team is approaching that work. Would a short call next week be useful?\n\n"
                                f"{{sender_name}}",
                        "cites": [n1]},
    }
    return json.dumps(brief), {"ms": 0, "input_tokens": 0, "output_tokens": 0, "cache_write_tokens": 0,
                               "cache_read_tokens": 0, "cost_usd": 0.0, "model": "stand-in"}
