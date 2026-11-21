"""The Census Bureau's Gazetteer national places file: every incorporated place and census-designated place in the
United States with its state and its internal point. Public domain, as a work of the U.S. government.

owner/bootstrap.sh downloads it into data/raw/gazetteer/ (gitignored). The pipeline keeps only the places the postings
use, in config/cities.csv, so a clean clone of the public repo builds from that small file alone.

    python3 -m engine.gazetteer --check      the file, its columns and how many places it holds
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
RAW = HERE.joinpath("data", "raw", "gazetteer")
NEEDED = ("USPS", "NAME", "LSAD", "ALAND", "INTPTLAT", "INTPTLONG")
CITY = "25"  # the LSAD code for an incorporated city, preferred over a CDP of the same name
SUFFIXES = sorted((" city and borough", " city", " town", " village", " borough", " cdp", " municipality",
                   " metropolitan government", " metro government", " urban county", " unified government",
                   " consolidated government", " corporation", " plantation", " comunidad", " zona urbana"),
                  key=len, reverse=True)


def find(folder=None):
    """The newest *_Gaz_place_national.txt in the folder, or None."""
    files = sorted(Path(folder or RAW).glob("*_Gaz_place_national.txt"))
    return files[-1] if files else None


def clean(name):
    """'Denver city' to 'Denver', and the aliases a posting might use for a consolidated city."""
    base = re.sub(r"\s*\(balance\)\s*$", "", name.strip())
    low = base.lower()
    for s in SUFFIXES:
        if low.endswith(s) and len(base) > len(s):
            base = base[:-len(s)].strip()
            break
    names = [base]
    paren = re.match(r"^(.*?)\s*\((.*?)\)$", base)
    if paren:
        names += [paren.group(1).strip(), paren.group(2).strip()]
    for sep in ("-", "/"):
        if sep in base:
            names.append(base.split(sep)[0].strip())
    if base.startswith("Urban "):
        names.append(base[len("Urban "):])
    return names[0], [n for n in dict.fromkeys(names) if n]


def _text(path):
    raw = Path(path).read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def read(path):
    """Every place: {state, name, names, lsad, aland, lat, lon}."""
    lines = _text(path).lstrip("\ufeff").splitlines()
    sep = "\t" if "\t" in lines[0] else ("|" if "|" in lines[0] else ",")  # 2025 switched from tabs to pipes
    header = [h.strip() for h in lines[0].split(sep)]
    missing = [c for c in NEEDED if c not in header]
    if missing:
        raise ValueError(f"the Gazetteer file is missing the columns {', '.join(missing)}")
    at = {c: header.index(c) for c in NEEDED}
    out = []
    for line in lines[1:]:
        cells = [c.strip() for c in line.split(sep)]
        if len(cells) < len(header):
            continue
        name, names = clean(cells[at["NAME"]])
        try:
            out.append({"state": cells[at["USPS"]], "name": name, "names": names, "lsad": cells[at["LSAD"]],
                        "aland": int(cells[at["ALAND"]] or 0), "lat": float(cells[at["INTPTLAT"]]),
                        "lon": float(cells[at["INTPTLONG"]])})
        except ValueError:
            continue
    return out


def index(places):
    """{(state, lower-case name): place}, preferring an incorporated city to a CDP, then the larger land area."""
    best = {}
    for p in places:
        rank = (p["lsad"] == CITY, p["aland"])
        for n in p["names"]:
            key = (p["state"], n.lower())
            if key not in best or rank > best[key][0]:
                best[key] = (rank, p)
    return {k: v[1] for k, v in best.items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check the Gazetteer places file.")
    ap.add_argument("--check", action="store_true")
    ap.parse_args(argv)
    path = find()
    if not path:
        print("No Gazetteer places file in data/raw/gazetteer/ yet. Run bash owner/bootstrap.sh.")
        return 1
    places = read(path)
    states = {p["state"] for p in places}
    print(f"{path.name}: {len(places):,} places in {len(states)} states and territories, with every column the build needs.")
    return 0 if len(places) > 20000 else 1


if __name__ == "__main__":
    sys.exit(main())
