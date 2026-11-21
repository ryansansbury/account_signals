"""Read the public job board JSON that Greenhouse, Lever and Ashby return into one shape of posting.

Each posting holds its id (provider:token:job_id), title, department, the raw location strings, any structured places
the provider gives (city, region and country), whether it's remote when the provider says, the public URL, the date and
the kind of date, whether it's a temporary role or an evergreen one, the plain text, and the company name a job carries.

Greenhouse gives first_published on some boards and only updated_at on others. An update date makes a posting look
fresher than it is, so every date keeps its kind (published, created or updated) and the page names it. Exact repeats of
a posting across cities fold into one posting with several locations. Evergreen postings ("general application,"
"talent community") are kept and marked, and they never score. The plain text stays in memory and in data/raw/, and only
the redacted excerpts behind the signals are ever stored.
"""
import hashlib
import html
import json
import re
from datetime import date, datetime, timezone

TAG = re.compile(r"<[^>]+>")
SPACE = re.compile(r"\s+")
BLOCK = re.compile(r"</?(p|div|li|ul|ol|br|h[1-6]|tr|section)\b[^>]*>", re.I)
BULLET = re.compile(r"(?m)^\s*(?:[-•*·▪●◦]|\d+[.)])\s+")
TEMPORARY = re.compile(r"\b(?:contract(?:or)?|contract[- ]to[- ]hire|temporary|temp|intern|internship|part[- ]time|"
                       r"seasonal|fixed[- ]term|co-?op)\b", re.I)
EVERGREEN = re.compile(r"general application|talent (?:community|pool|network)|future (?:opportunit|opening|role)|"
                       r"don'?t see (?:a|the|your)|join our talent|expression of interest|open application|"
                       r"speculative application|general interest|always hiring", re.I)
TEMP_TYPES = {"parttime", "intern", "contract", "temporary", "parttimecontract", "seasonal"}


def plain(markup):
    """HTML (sometimes escaped twice) to plain text with sentence breaks kept."""
    text = html.unescape(markup or "")
    text = html.unescape(text) if "&lt;" in text or "&amp;" in text else text
    text = BLOCK.sub(". ", text)
    text = TAG.sub(" ", text)
    text = html.unescape(text)
    text = re.sub(r"(\.\s*){2,}", ". ", text)
    text = re.sub(r"\s*[;,]+\s*\.", ".", text)
    text = re.sub(r"([!?:])\s*\.", r"\1", text)
    return SPACE.sub(" ", text).strip(" .")


def normalize(text):
    """Plain text with line breaks and bullets: each line becomes its own sentence, then spaces collapse."""
    text = BULLET.sub("", (text or "").replace("\r", ""))
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return SPACE.sub(" ", " ".join(ln if ln[-1] in ".!?:;" else ln.rstrip(",") + "." for ln in lines)).strip()


def joined(parts):
    """Plain-text pieces joined into one text with exactly one sentence break between them."""
    out = []
    for part in (SPACE.sub(" ", p).strip() for p in parts if p and p.strip()):
        out.append(part if part[-1] in ".!?:" else part + ".")
    return " ".join(out)


def pacific_day(stamp):
    """The Pacific date of an ISO timestamp, since every date the page shows is Pacific."""
    from zoneinfo import ZoneInfo
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()


def day(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date()
    s = str(value)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None


def _address(a):
    p = ((a or {}).get("postalAddress") or {}) if isinstance(a, dict) else {}
    out = {k: (p.get(f) or "").strip() for k, f in (("city", "addressLocality"), ("region", "addressRegion"),
                                                    ("country", "addressCountry"))}
    return out if any(out.values()) else None


def _temporary(title, kind=""):
    return bool(TEMPORARY.search(title or "")) or re.sub(r"[^a-z]", "", (kind or "").lower()) in TEMP_TYPES


def greenhouse(token, data):
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "") or ""
        if not loc:
            loc = "; ".join(o.get("location") or o.get("name") or "" for o in j.get("offices") or [] if o)
        published = j.get("first_published")
        out.append({"job_id": str(j.get("id", "")), "title": j.get("title", "") or "",
                    "department": ", ".join(d.get("name", "") for d in j.get("departments") or [] if d),
                    "locations": [loc] if loc else [], "places": [], "remote": None,
                    "url": j.get("absolute_url", "") or "", "posted": day(published or j.get("updated_at")),
                    "date_kind": "published" if published else "updated",
                    "employment": "temporary" if _temporary(j.get("title")) else "",
                    "text": plain(j.get("content", "")), "company": j.get("company_name") or ""})
    return out


def lever(token, data):
    out = []
    for j in data if isinstance(data, list) else []:
        cats = j.get("categories") or {}
        parts = [normalize(j.get("descriptionPlain")) or plain(j.get("description", ""))]
        for block in j.get("lists") or []:
            parts.append(f"{block.get('text', '')}. {plain(block.get('content', ''))}")
        parts.append(normalize(j.get("additionalPlain")) or plain(j.get("additional", "")))
        locs = [x for x in (cats.get("allLocations") or []) if x] or ([cats["location"]] if cats.get("location") else [])
        kind = (j.get("workplaceType") or "").lower()
        out.append({"job_id": str(j.get("id", "")), "title": j.get("text", "") or "",
                    "department": cats.get("department") or cats.get("team") or "", "locations": locs,
                    "places": [{"city": "", "region": "", "country": j["country"]}] if j.get("country") else [],
                    "remote": True if kind == "remote" else (False if kind in ("hybrid", "onsite", "on-site") else None),
                    "url": j.get("hostedUrl", "") or "", "posted": day(j.get("createdAt")), "date_kind": "created",
                    "employment": "temporary" if _temporary(j.get("text"), cats.get("commitment")) else "",
                    "text": joined(parts), "company": ""})
    return out


def ashby(token, data):
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        loc = j.get("location") or ""
        if isinstance(loc, dict):
            loc = loc.get("name", "")
        locs = [loc] if loc else []
        places = [p for p in [_address(j.get("address"))] if p]
        for s in j.get("secondaryLocations") or []:
            if isinstance(s, dict):
                if s.get("location"):
                    locs.append(s["location"])
                p = _address(s.get("address"))
                if p:
                    places.append(p)
        work = (j.get("workplaceType") or "").lower()
        remote = True if (j.get("isRemote") or work == "remote") else (False if work in ("hybrid", "onsite") else None)
        out.append({"job_id": str(j.get("id", "")), "title": j.get("title", "") or "",
                    "department": j.get("department") or j.get("team") or "", "locations": locs, "places": places,
                    "remote": remote, "url": j.get("jobUrl") or j.get("applyUrl") or "",
                    "posted": day(j.get("publishedAt") or j.get("updatedAt")),
                    "date_kind": "published" if j.get("publishedAt") else "updated",
                    "employment": "temporary" if _temporary(j.get("title"), j.get("employmentType")) else "",
                    "text": normalize(j.get("descriptionPlain")) or plain(j.get("descriptionHtml", "")), "company": ""})
    return out


PARSERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}


def parse(provider, token, raw):
    """Every posting on one board, with exact repeats (the same job listed in several cities) folded together."""
    data = json.loads(raw) if isinstance(raw, (bytes, str)) else raw
    seen, out = {}, []
    for p in PARSERS[provider](token, data):
        key = hashlib.sha1((p["title"].strip().lower() + "|" + p["text"][:4000]).encode()).hexdigest()
        if key in seen:
            first = seen[key]
            first["locations"] += [x for x in p["locations"] if x not in first["locations"]]
            first["places"] += [x for x in p["places"] if x not in first["places"]]
            first["repeats"] += 1
            continue
        p.update(provider=provider, token=token, id=f"{provider}:{token}:{p['job_id']}", repeats=1,
                 evergreen=bool(EVERGREEN.search(p["title"])))
        seen[key] = p
        out.append(p)
    return out
