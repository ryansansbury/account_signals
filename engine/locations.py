"""Where a posting is: a US city, somewhere in the US without a city, remote in the US, outside the US, or unknown.

Structured fields come first (Ashby's address, Lever's country code), then the free text. The text is split on ";",
"|", "/" and " or ", and each part is read for remote words, a country, a state by name or postal code, and a city. A
city with a state is matched to a Census Bureau Gazetteer place. A city without a state goes through a short list of
aliases ("Bay Area," "NYC") and large cities. Remote without a country counts as remote in the US, since every company
in the universe is a US company, and DATA.md says so.

Each part comes back as {kind, city, state, lat, lon}, where kind is city, us, remote, nonus or unknown.
"""
import re

from engine.geo import STATES

STATE_NAMES = {v.lower(): k for k, v in STATES.items()}
STATE_NAMES.update({"washington dc": "DC", "washington d.c.": "DC", "d.c.": "DC"})
US = {"us", "u.s.", "usa", "u.s.a.", "united states", "united states of america", "america", "us-based", "us based",
      "nationwide", "north america"}
NON_US_SINGLE = set("""canada mexico uk u.k. germany france spain portugal italy netherlands belgium switzerland austria
sweden norway denmark finland poland czechia romania ukraine israel india singapore japan china taiwan korea australia
brazil argentina colombia chile peru philippines vietnam indonesia malaysia thailand uae turkey egypt kenya nigeria emea
apac latam europe asia africa anz dach nordics benelux eu england scotland wales ireland""".split())
NON_US = NON_US_SINGLE | {"united kingdom", "south korea", "new zealand", "czech republic", "hong kong", "south africa",
                          "saudi arabia", "united arab emirates", "latin america"}
NON_US_CITIES = set("""london toronto vancouver montreal montréal dublin berlin munich paris amsterdam madrid barcelona
lisbon stockholm copenhagen oslo helsinki warsaw krakow prague zurich zürich geneva vienna bangalore bengaluru hyderabad
pune mumbai delhi gurgaon gurugram noida chennai tokyo sydney melbourne auckland bogota bogotá manila seoul shanghai
beijing shenzhen taipei dubai lagos nairobi cairo istanbul edinburgh manchester belfast cork galway ottawa calgary
edmonton waterloo kitchener halifax guadalajara monterrey medellin medellín santiago lima kyiv bucharest sofia belgrade
budapest athens milan rome hamburg frankfurt cologne stuttgart brussels antwerp rotterdam utrecht eindhoven luxembourg
tallinn riga vilnius reykjavik""".split()) | {"tel aviv", "mexico city", "sao paulo", "são paulo", "buenos aires",
                                              "ho chi minh city", "cape town", "the hague", "quebec city"}
PROVINCES = {"on", "qc", "bc", "ab", "mb", "sk", "ns", "nb", "nl", "pe", "ontario", "quebec", "british columbia",
             "alberta", "manitoba", "saskatchewan", "nova scotia", "new brunswick"}
ALIASES = {
    "bay area": ("San Francisco", "CA"), "sf bay area": ("San Francisco", "CA"),
    "san francisco bay area": ("San Francisco", "CA"), "sf": ("San Francisco", "CA"), "silicon valley": ("San Jose", "CA"),
    "nyc": ("New York", "NY"), "new york city": ("New York", "NY"), "new york metro": ("New York", "NY"),
    "manhattan": ("New York", "NY"), "brooklyn": ("New York", "NY"), "dc": ("Washington", "DC"),
    "washington dc": ("Washington", "DC"), "washington d.c.": ("Washington", "DC"), "dc metro": ("Washington", "DC"),
    "la": ("Los Angeles", "CA"), "greater los angeles": ("Los Angeles", "CA"), "greater boston": ("Boston", "MA"),
    "boston area": ("Boston", "MA"), "twin cities": ("Minneapolis", "MN"), "minneapolis-st. paul": ("Minneapolis", "MN"),
    "dfw": ("Dallas", "TX"), "dallas-fort worth": ("Dallas", "TX"), "dallas fort worth": ("Dallas", "TX"),
    "research triangle": ("Raleigh", "NC"), "rtp": ("Raleigh", "NC"), "raleigh-durham": ("Raleigh", "NC"),
    "chicagoland": ("Chicago", "IL"), "greater chicago": ("Chicago", "IL"), "denver metro": ("Denver", "CO"),
    "front range": ("Denver", "CO"), "greater phoenix": ("Phoenix", "AZ"), "metro atlanta": ("Atlanta", "GA"),
    "greater seattle": ("Seattle", "WA"), "puget sound": ("Seattle", "WA"), "greater austin": ("Austin", "TX"),
    "greater houston": ("Houston", "TX"), "philly": ("Philadelphia", "PA"), "greater philadelphia": ("Philadelphia", "PA"),
    "saint louis": ("St. Louis", "MO"), "st louis": ("St. Louis", "MO"), "salt lake": ("Salt Lake City", "UT"),
    "slc": ("Salt Lake City", "UT"), "nola": ("New Orleans", "LA"),
}
MAJOR = {c: s for s, cities in {
    "CA": "san francisco|los angeles|san diego|san jose|palo alto|mountain view|menlo park|sunnyvale|santa clara|"
          "redwood city|oakland|irvine|santa monica|sacramento|berkeley|emeryville|south san francisco|pasadena|"
          "san mateo|cupertino|fremont|long beach|el segundo|culver city|burlingame",
    "NY": "new york|buffalo|rochester|albany", "MA": "boston|cambridge|somerville|waltham|burlington|woburn",
    "WA": "seattle|bellevue|redmond|kirkland|tacoma|spokane", "TX": "austin|dallas|houston|san antonio|plano|irving|"
                                                                   "fort worth|frisco|the woodlands",
    "IL": "chicago", "CO": "denver|boulder|colorado springs|fort collins|golden|broomfield|englewood|aurora|lakewood",
    "GA": "atlanta|alpharetta", "FL": "miami|tampa|orlando|jacksonville|fort lauderdale|boca raton|st. petersburg",
    "AZ": "phoenix|scottsdale|tempe|tucson|chandler", "PA": "philadelphia|pittsburgh", "UT": "salt lake city|lehi|provo|"
                                                                                          "draper|ogden",
    "TN": "nashville|memphis|chattanooga|knoxville", "MN": "minneapolis|st. paul", "OR": "portland|beaverton|bend",
    "MI": "detroit|ann arbor|grand rapids", "OH": "columbus|cincinnati|cleveland", "NC": "charlotte|raleigh|durham",
    "MD": "baltimore|bethesda", "MO": "st. louis|kansas city", "IN": "indianapolis", "WI": "milwaukee|madison",
    "NV": "las vegas|reno", "VA": "arlington|reston|richmond|mclean", "NJ": "jersey city|hoboken|newark|princeton",
    "DC": "washington", "KY": "louisville|lexington", "LA": "new orleans", "AL": "birmingham|huntsville",
    "RI": "providence", "CT": "hartford|stamford|new haven", "NE": "omaha|lincoln", "ID": "boise", "NM": "albuquerque",
    "OK": "oklahoma city|tulsa", "IA": "des moines", "SC": "charleston|greenville", "HI": "honolulu", "AK": "anchorage",
}.items() for c in cities.split("|")}
REMOTE = re.compile(r"\bremote\b|\banywhere\b|work from home|\bwfh\b|\bdistributed\b|\bvirtual\b", re.I)
WORKPLACE = re.compile(r"\b(?:remote|hybrid|on-?site|in[- ]office|office|anywhere|work from home|wfh|distributed|"
                       r"virtual|based|first|friendly|eligible|optional|preferred|only|within|in the)\b", re.I)
SPLIT = re.compile(r"\s*(?:;|\||/|\bor\b|\n|\s-\s(?=[A-Z][a-z]+,))\s*")


def _gaz(index, city, state):
    if not index or not city:
        return None
    c = city.strip().lower()
    for v in (c, c.replace("st. ", "saint "), c.replace("saint ", "st. "), c.replace("ft. ", "fort "),
              c.replace("mt. ", "mount ")):
        hit = index.get((state, v))
        if hit:
            return hit
    return None


def _city(city, state, index):
    hit = _gaz(index, city, state)
    if hit:
        return {"kind": "city", "city": hit["name"], "state": state, "lat": hit["lat"], "lon": hit["lon"]}
    return {"kind": "us", "city": "", "state": state}


def _state(token):
    t = token.strip().strip(".").lower()
    if token.strip().upper() in STATES and len(token.strip()) == 2:
        return token.strip().upper()
    return STATE_NAMES.get(t)


def part(raw, index=None, remote_hint=None):
    """One location string to {kind, city, state, lat, lon}."""
    text = re.sub(r"[()\[\]]", " ", raw or "").replace("–", "-").replace("—", "-").strip()
    low = text.lower().strip(" .,-")
    if not low:
        return {"kind": "unknown"}
    if low in ALIASES:
        return _city(*ALIASES[low], index)
    remote = bool(REMOTE.search(text)) or remote_hint is True
    rest = WORKPLACE.sub(" ", text)
    rest = re.sub(r"\s*-\s*", ", ", rest)
    tokens = [t.strip(" .-") for t in rest.split(",") if t.strip(" .-")]
    country = None
    if tokens and tokens[-1].lower() in US:
        country = "us"
        tokens = tokens[:-1]
    elif tokens and (tokens[-1].lower() in NON_US or tokens[-1].lower() in NON_US_SINGLE):
        return {"kind": "nonus"}
    if tokens and tokens[-1].lower() in PROVINCES and len(tokens) >= 2:
        return {"kind": "nonus"}
    if len(tokens) >= 2 and _state(tokens[-1]):
        st = _state(tokens[-1])
        return _city(tokens[-2], st, index)
    if len(tokens) == 1:
        t = tokens[0].lower()
        if t in ALIASES:
            return _city(*ALIASES[t], index)
        st = _state(tokens[0])
        if st and t not in MAJOR:
            return {"kind": "us", "city": "", "state": st}
        if t in MAJOR:
            return _city(tokens[0], MAJOR[t], index)
        if t in NON_US_CITIES or t in NON_US or t in NON_US_SINGLE:
            return {"kind": "nonus"}
        if t in US:
            return {"kind": "remote" if remote else "us", "city": "", "state": ""}
    if not tokens:
        if remote or country == "us":
            return {"kind": "remote" if remote else "us", "city": "", "state": ""}
        return {"kind": "unknown"}
    if remote:
        return {"kind": "remote", "city": "", "state": ""}
    if country == "us":
        return {"kind": "us", "city": "", "state": ""}
    return {"kind": "unknown"}


def read(posting, index=None):
    """Every place one posting names, structured fields first, without repeats."""
    out = []
    for p in posting.get("places") or []:
        country = (p.get("country") or "").strip().lower()
        if country and country not in US:
            out.append({"kind": "nonus"})
            continue
        st = _state(p.get("region") or "")
        if p.get("city") and st:
            out.append(_city(p["city"], st, index))
    structured_us = any((p.get("country") or "").strip().lower() in US for p in posting.get("places") or [])
    if not [o for o in out if o["kind"] == "city"]:
        for raw in posting.get("locations") or []:
            for piece in (x for x in SPLIT.split(raw) if x and x.strip()):
                got = part(piece, index, posting.get("remote"))
                if got["kind"] == "unknown" and structured_us:
                    got = {"kind": "us", "city": "", "state": ""}
                out.append(got)
    if not out and (posting.get("remote") is True or structured_us):
        out.append({"kind": "remote" if posting.get("remote") else "us", "city": "", "state": ""})
    seen, unique = set(), []
    for o in out or [{"kind": "unknown"}]:
        key = (o["kind"], o.get("city", ""), o.get("state", ""))
        if key not in seen:
            seen.add(key)
            unique.append(o)
    return unique


def region_of(place):
    """'us', 'nonus' or 'unknown' for one posting's places: US when any place is in the US."""
    kinds = {p["kind"] for p in place}
    if kinds & {"city", "us", "remote"}:
        return "us"
    if "nonus" in kinds:
        return "nonus"
    return "unknown"
