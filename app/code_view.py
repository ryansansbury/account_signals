"""The code section on How it works: excerpts of the project's real files, copied in on every build so they never drift
from the code they show. Each file shows its opening explanation when that's short, then the functions and constants
named below, each line under the number it has in its file. No file goes in whole, and none of the page's own scripts
but site/scoring.js, the page's copy of the scoring.

The excerpts go to site/code.js as data apart from the page's script, and How it works loads that file when it opens.
A name below that's missing from its file stops the build, so an excerpt can't quietly go stale.
"""
import ast
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
EXCERPTS = {
    "agents/judge.py": ("check", "plant"),
    "engine/boards.py": ("greenhouse", "lever"),
    "engine/claims.py": ("check_brief", "sources_for"),
    "engine/exclusions.py": ("full", "core", "variants"),
    "engine/geo.py": ("conic_equal_area", "project"),
    "engine/redact.py": ("EMAIL", "PHONE", "LINK", "HANDLE", "redact"),
    "engine/route.py": ("business_days", "route"),
    "engine/score.py": ("decay", "age_of", "signal_points", "intent", "fit", "tier_of", "score"),
    "engine/signals.py": ("find", "strength"),
    "evals/freeze.py": ("changed", "freeze"),
    "owner/fetch.py": ("HOSTS", "ALLOWED_HOSTS", "ALLOWED_PATHS", "check_url", "pace", "robots_ok"),
    "owner/record_briefs.py": ("attempt", "record_one"),
    "site/scoring.js": ("decay", "ageOf", "signalPoints", "intent"),
}
DEFAULT = "engine/score.py"
OPENING_MAX = 16


def _python_spans(text, names):
    tree = ast.parse(text)
    spans, found = [], set()
    first = tree.body[0] if tree.body else None
    if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) and \
            isinstance(first.value.value, str) and first.end_lineno - first.lineno < OPENING_MAX:
        spans.append((first.lineno, first.end_lineno))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            name = node.name
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        else:
            continue
        if name in names:
            start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            spans.append((start, node.end_lineno))
            found.add(name)
    return spans, found


def _js_spans(lines, names):
    spans, found = [], set()
    if lines and lines[0].startswith("/*"):
        end = next((i for i, ln in enumerate(lines) if "*/" in ln), None)
        if end is not None and end < OPENING_MAX:
            spans.append((1, end + 1))
    for name in names:
        head = re.compile(r"^(\s*)function " + re.escape(name) + r"\(")
        for i, ln in enumerate(lines):
            m = head.match(ln)
            if m:
                end = next((j for j in range(i + 1, len(lines)) if lines[j] == m.group(1) + "}"), None)
                if end is not None:
                    spans.append((i + 1, end + 1))
                    found.add(name)
                break
    return spans, found


def excerpt(rel, names, root=HERE):
    """{lines: the file's length, parts: [[first line number, text], ...]} with neighbors joined across blank lines."""
    text = Path(root).joinpath(*rel.split("/")).read_text(encoding="utf-8")
    lines = text.splitlines()
    spans, found = (_js_spans(lines, names) if rel.endswith(".js") else _python_spans(text, names))
    missing = [n for n in names if n not in found]
    if missing:
        raise ValueError(f"the code view's excerpt of {rel} names {', '.join(missing)}, which it doesn't hold")
    parts = []
    for a, b in sorted(spans):
        if parts and all(not ln.strip() for ln in lines[parts[-1][1]:a - 1]):
            parts[-1][1] = max(parts[-1][1], b)
        else:
            parts.append([a, b])
    shown = sum(b - a + 1 for a, b in parts)
    if shown >= len(lines):
        raise ValueError(f"the code view's excerpt of {rel} is the whole file")
    return {"lines": len(lines), "parts": [[a, "\n".join(lines[a - 1:b])] for a, b in parts]}


def collect(featured=(), root=HERE):
    files = {rel: excerpt(rel, names, root) for rel, names in EXCERPTS.items()}
    absent = [f for f in featured if f not in files]
    if absent:
        raise ValueError(f"the featured files {', '.join(absent)} have no excerpt in app/code_view.py")
    return files


def write(words, path=None):
    files = collect(words.table("ui.how.code.files"))
    path = Path(path or HERE.joinpath("site", "code.js"))
    path.write_text("window.AS_CODE = " + json.dumps({"default": DEFAULT, "files": files}, ensure_ascii=False,
                                                     separators=(",", ":")) + ";\n", encoding="utf-8")
    return path.stat().st_size
