"""Read a model's reply as the brief's JSON and check its shape, before any claim is checked.

A reply may wrap the object in a code fence or put a sentence before it, so the first JSON object in it is taken. The
shape must match prompts/brief.md: why_now as a list of {text}, priority as {text}, questions and unknowns as lists of
strings, and first_touch as {subject, body, cites} with cites a list of whole numbers. Anything else is an error the
recorder sends back in its one repair request.
"""
import json
import re


def first_object(text):
    """The first JSON object in the text, or None."""
    text = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", (text or "").strip())
    start = text.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except ValueError:
                    return None
    return None


def check(text):
    """(brief, []) when the reply has the right shape, or (None, [errors])."""
    data = first_object(text)
    if not isinstance(data, dict):
        return None, ["the reply isn't one JSON object"]
    errors = []
    why = data.get("why_now")
    if not isinstance(why, list) or not all(isinstance(x, dict) and isinstance(x.get("text"), str) for x in why):
        errors.append("why_now must be a list of objects with a text string")
    pr = data.get("priority")
    if not isinstance(pr, dict) or not isinstance(pr.get("text"), str):
        errors.append("priority must be an object with a text string")
    for key in ("questions", "unknowns"):
        v = data.get(key)
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            errors.append(f"{key} must be a list of strings")
    ft = data.get("first_touch")
    if not isinstance(ft, dict) or not isinstance(ft.get("subject"), str) or not isinstance(ft.get("body"), str):
        errors.append("first_touch must be an object with subject and body strings")
    elif not isinstance(ft.get("cites"), list) or not all(isinstance(c, int) and not isinstance(c, bool)
                                                           for c in ft["cites"]):
        errors.append("first_touch.cites must be a list of whole numbers")
    return (None, errors) if errors else (data, [])
