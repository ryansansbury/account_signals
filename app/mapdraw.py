"""The states for the page's map: the Census Bureau's boundaries from data/map/states-albers-10m.json as SVG paths in
whole pixels, plus the nation's outline. The page draws them once and places the accounts' bubbles on top with the same
Albers USA frame (975 by 610) that engine/rank.py uses for each hub.

Each arc is simplified once, so borders that two states share stay shared. An arc that closes on itself, such as an
island or all of Alaska's and Hawaii's coasts, has no line between its ends to measure from, so it's split at its
farthest point and each half is simplified on its own. Without that, every island ring collapsed to nothing and the
insets went missing.

The Aleutian Islands reach about 58 pixels left of the frame's zero, so the drawing's frame starts at its own left edge
("x" below) and the page's view box starts there too. The hubs keep the frame engine/rank.py gives them.
"""
import json
import math

from engine import geo

SKIP = ("Puerto Rico", "Guam", "American Samoa", "Commonwealth of the Northern Mariana Islands",
        "United States Virgin Islands")


def simplify_arc(points, tolerance):
    if tolerance > 0 and len(points) > 4 and tuple(points[0]) == tuple(points[-1]):
        x0, y0 = points[0]
        far = max(range(1, len(points) - 1), key=lambda i: (points[i][0] - x0) ** 2 + (points[i][1] - y0) ** 2)
        a = geo.simplify(points[:far + 1], tolerance)
        b = geo.simplify(points[far:], tolerance)
        return list(a[:-1]) + list(b)
    return geo.simplify(points, tolerance)


def shapes(tolerance=0.6, topo_path=None):
    topo = json.loads((topo_path or geo.TOPO).read_text(encoding="utf-8"))
    arcs = [simplify_arc(a, tolerance) for a in geo.decode_arcs(topo)]
    named = {}
    for g in topo["objects"]["states"]["geometries"]:
        name = (g.get("properties") or {}).get("name")
        if name and name not in SKIP:
            named[name] = geo.polygons(g, arcs)
    nation = []
    for g in topo.get("objects", {}).get("nation", {}).get("geometries", []):
        nation.extend(geo.polygons(g, arcs))
    codes = {v: k for k, v in geo.STATES.items()}
    states = [{"name": name, "code": codes.get(name, ""), "d": geo.path_d(polys)} for name, polys in sorted(named.items())]
    xs = [x for polys in list(named.values()) + [nation] for poly in polys for r in poly for x, _ in r]
    left = min(0, math.floor(min(xs)) - 2) if xs else 0
    return {"x": left, "width": geo.WIDTH - left, "height": geo.HEIGHT, "states": states, "nation": geo.path_d(nation)}
