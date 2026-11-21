"""Posting text is untrusted web text, and its excerpts reach the models and the page, so each one is checked first.

clean() removes characters a person can't see but a model reads (zero-width spaces, direction marks, soft hyphens),
which turn up in ordinary copy-pasted postings. suspicious() names anything that reads as a planted message: tag
characters or private-use characters that can carry hidden text, and phrasing aimed at a model, such as "ignore your
instructions" or "you are now". The pipeline drops a suspicious excerpt and counts it.
"""
import re
import unicodedata

PHRASING = [
    re.compile(r"\b(?:ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}"
               r"\b(?:instructions?|prompts?|rules|guidelines|above|previous|prior|earlier)\b", re.I),
    re.compile(r"\b(?:new|updated|additional|hidden|real|actual)\s+instructions?\b", re.I),
    re.compile(r"\bsystem\s+(?:prompt|message)\b", re.I),
    re.compile(r"\b(?:you are now|from now on,? you|pretend (?:to be|you are)|role-?play as)\b", re.I),
    re.compile(r"\b(?:if )?you(?:'re| are)\s+(?:an?\s+)?(?:llm|(?:large )?language model|chatbot"
               r"|ai (?:assistant|agent|model))\b", re.I),
    re.compile(r"\b(?:dear|attention|note to|notes? for|message to|message for|instructions? for|hey)"
               r"\s+(?:the\s+|any\s+)?(?:ai|llm|assistant|agent|bot|model|claude|chatgpt|gpt|gemini|copilot)s?\b",
               re.I),
    re.compile(r"^\s*(?:system|assistant|user|human|developer)\s*:", re.I),
    re.compile(r"<\|[\w-]+\|>|\[/?INST\]|<<SYS>>", re.I),
    re.compile(r"\b(?:run|execute|paste)\s+(?:this|the following|these)\b", re.I),
    re.compile(r"\b(?:visit|open|click|go to|navigate to|fetch|load)\b[^.\n]{0,25}https?:", re.I),
]
INVISIBLE = {0x00AD, 0x180E, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF,
             0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069}


def clean(text):
    """The text without invisible formatting characters and control characters (tabs and line breaks become spaces)."""
    out = []
    for ch in text or "":
        cp = ord(ch)
        if cp in INVISIBLE or 0xFE00 <= cp <= 0xFE0F:
            continue
        if ch in "\t\r\n":
            out.append(" ")
            continue
        if cp < 32 or cp == 127:
            continue
        out.append(ch)
    return "".join(out)


def suspicious(text):
    """A short reason when the text holds hidden characters or reads like a message to a model, else ''."""
    for ch in text or "":
        cp = ord(ch)
        if 0xE0000 <= cp <= 0xE007F:
            return "tag characters"
        cat = unicodedata.category(ch)
        if cat == "Co":
            return "private-use characters"
        if cat == "Cf" and cp not in INVISIBLE:
            return "format characters"
    if any(p.search(text or "") for p in PHRASING):
        return "phrasing aimed at a model"
    return ""
