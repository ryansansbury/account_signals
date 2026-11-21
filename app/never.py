"""Words that must never ship, and the scan that enforces it.

Two lists. The never list comes from tools/lint_copy.py's never-word tuple and reference/private_words.txt (a line written
rot13:... is decoded first), and neither file ships. The foreign list, config/foreign_words.txt, holds the other demos'
companies and people, since each project stands alone. A match is a whole word
or phrase without regard to case, so "cat" never matches "category." A hit is reported by file with a count, and a word
from the never list is never printed. The private exclusion list has its own scan in engine/exclusions.py.
"""
import codecs
import importlib.util
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def words(private=None, tool=None):
    out = []
    private = Path(private or HERE.joinpath("reference", "private_words.txt"))
    if private.exists():
        for line in private.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(codecs.decode(line[6:], "rot13").lower() if line.startswith("rot13:") else line.lower())
    tool = Path(tool or HERE.joinpath("tools", "lint_copy.py"))
    if tool.exists():
        spec = importlib.util.spec_from_file_location("lint_copy_never", str(tool))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out += [w.lower() for w in getattr(mod, "never".upper(), ())]
    return tuple(dict.fromkeys(out))


def _list(path):
    path = Path(path)
    if not path.exists():
        return ()
    return tuple(line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.strip().startswith("#"))


def foreign(path=None):
    return _list(path or HERE.joinpath("config", "foreign_words.txt"))


def pattern(word_list):
    parts = [r"\b" + re.escape(w).replace(r"\ ", r"\s+") + r"\b" for w in word_list]
    return re.compile("|".join(parts), re.IGNORECASE) if parts else None


def hits(text, word_list):
    pat = pattern(word_list)
    if not pat:
        return []
    return list(dict.fromkeys(m.group(0).lower() for m in pat.finditer(text)))


def clean(text, never_words=None, foreign_words=None):
    """True when a piece of text (an excerpt, a brief) holds nothing from either list."""
    never_words = words() if never_words is None else never_words
    foreign_words = foreign() if foreign_words is None else foreign_words
    return not hits(text, never_words) and not hits(text, foreign_words)


def scan(paths, never_words=None, foreign_words=None):
    """A line per file that holds a never-word or another demo's name. The never-words themselves are never printed."""
    never_words = words() if never_words is None else never_words
    foreign_words = foreign() if foreign_words is None else foreign_words
    problems = []
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        n, f = hits(text, never_words), hits(text, foreign_words)
        if n:
            problems.append(f"{path.name} holds {len(n)} word(s) from the never list")
        if f:
            problems.append(f"{path.name} names another demo's company or person: {', '.join(f)}")
    return problems
