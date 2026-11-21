"""The map's geometry: the states from the Census Bureau's boundaries and Albers USA for every city, with the check that
each city lands inside its own state.

data/map/states-albers-10m.json is the us-atlas TopoJSON of the Census Bureau's cartographic boundary files (public
domain, ISC-licensed packaging), already projected with d3.geoAlbersUsa at scale 1300 into a 975 by 610 frame with
Alaska and Hawaii as insets. project() repeats that projection for a latitude and longitude: the lower 48 as
d3 projects them, and d3's Alaska and Hawaii insets, chosen by the city's state. A point is inside a state when an
even-odd ray cast across every ring of the state's polygons says so. Standard library only.
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TOPO = HERE.joinpath("data", "map", "states-albers-10m.json")
WIDTH, HEIGHT = 975, 610
K, TX, TY = 1300, 487.5, 305

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


def conic_equal_area(lam, phi, p0, p1):
    """d3's conicEqualAreaRaw, every angle in radians."""
    s0 = math.sin(p0)
    n = (s0 + math.sin(p1)) / 2
    c = 1 + s0 * (2 * n - s0)
    r0 = math.sqrt(c) / n
    r = math.sqrt(c - 2 * n * math.sin(phi)) / n
    return r * math.sin(lam * n), r0 - r * math.cos(lam * n)


# (rotate, center longitude, center latitude, parallel 1, parallel 2, scale factor, x offset, y offset), from d3-geo's
# albersUsa: the lower 48, then Alaska at 0.35 of the scale, then Hawaii.
INSETS = {
    "lower48": (96, -0.6, 38.7, 29.5, 45.5, 1.0, 0.0, 0.0),
    "AK": (154, -2, 58.5, 55, 65, 0.35, -0.307, 0.201),
    "HI": (157, -3, 19.9, 8, 18, 1.0, -0.205, 0.212),
}


def project(lon, lat, state=None, k=K, tx=TX, ty=TY):
    """d3.geoAlbersUsa().scale(k).translate([tx, ty]) for a point, with the inset picked by its state."""
    rot, clon, clat, p0, p1, f, dx, dy = INSETS.get(state, INSETS["lower48"])
    p0, p1 = math.radians(p0), math.radians(p1)
    lam = math.radians(((lon + rot + 180) % 360) - 180)
    x, y = conic_equal_area(lam, math.radians(lat), p0, p1)
    xc, yc = conic_equal_area(math.radians(clon), math.radians(clat), p0, p1)
    s = k * f
    return tx + dx * k + s * (x - xc), ty + dy * k - s * (y - yc)


def decode_arcs(topo):
    t = topo.get("transform")
    out = []
    for arc in topo["arcs"]:
        if t:
            (sx, sy), (ox, oy) = t["scale"], t["translate"]
            x = y = 0
            pts = []
            for ax, ay in arc:
                x += ax
                y += ay
                pts.append((x * sx + ox, y * sy + oy))
        else:
            pts = [(p[0], p[1]) for p in arc]
        out.append(pts)
    return out


def ring(arcs, idxs):
    pts = []
    for i in idxs:
        a = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
        pts.extend(a[1:] if pts else a)
    return pts


def polygons(geom, arcs):
    if geom["type"] == "Polygon":
        return [[ring(arcs, r) for r in geom["arcs"]]]
    if geom["type"] == "MultiPolygon":
        return [[ring(arcs, r) for r in poly] for poly in geom["arcs"]]
    return []


def inside(pt, polys):
    """Even-odd ray casting across every ring, so holes count."""
    x, y = pt
    hit = False
    for poly in polys:
        for r in poly:
            for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]):
                if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                    hit = not hit
    return hit


def path_d(polys, digits=0):
    """An SVG path for the polygons, rounded to whole pixels by default, with repeated points dropped."""
    parts = []
    for poly in polys:
        for r in poly:
            pts = []
            for x, y in r:
                p = (round(x, digits), round(y, digits)) if digits else (int(round(x)), int(round(y)))
                if not pts or p != pts[-1]:
                    pts.append(p)
            if len(pts) >= 3:
                parts.append("M" + "L".join(f"{x},{y}" for x, y in pts) + "Z")
    return "".join(parts)


def simplify(points, tolerance):
    """Douglas-Peucker on one arc, keeping its endpoints, so borders that states share stay shared."""
    if tolerance <= 0 or len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = points[a], points[b]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy) or 1e-9
        far, at = 0.0, None
        for i in range(a + 1, b):
            px, py = points[i]
            d = abs(dy * (px - x1) - dx * (py - y1)) / norm
            if d > far:
                far, at = d, i
        if at is not None and far > tolerance:
            keep[at] = True
            stack += [(a, at), (at, b)]
    return [p for p, k in zip(points, keep) if k]


class Map:
    def __init__(self, path=None, tolerance=0.0):
        topo = json.loads(Path(path or TOPO).read_text(encoding="utf-8"))
        arcs = [simplify(a, tolerance) for a in decode_arcs(topo)]
        self.states = {}
        for g in topo["objects"]["states"]["geometries"]:
            name = (g.get("properties") or {}).get("name")
            if name:
                self.states[name] = polygons(g, arcs)
        self.nation = []
        for g in topo.get("objects", {}).get("nation", {}).get("geometries", []):
            self.nation.extend(polygons(g, arcs))

    def place(self, lat, lon, state):
        """(x, y) for a city, or None when it lands outside its own state."""
        x, y = project(lon, lat, state)
        polys = self.states.get(STATES.get(state, ""))
        return (x, y) if polys and inside((x, y), polys) else None
