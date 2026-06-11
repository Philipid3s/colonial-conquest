"""
Generate data/territories.py from Natural Earth 110m country boundaries.

Source: data/raw/countries-110m.json (world-atlas TopoJSON).
Countries are grouped into game territories; polygons of a group are merged
by cancelling arcs shared between members (TopoJSON merge), so internal
borders disappear while inter-territory borders stay exactly shared.
Land adjacency is computed from arcs shared between groups; sea links are
hand-defined below.

Run from the project root:  python tools/build_territories.py
"""
import json
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SRC = "data/raw/countries-110m.json"
OUT = "data/territories.py"

# ── territory configuration ───────────────────────────────────────────────────
# key → (display name, owner, income, [country names], flags)
# owner None = NEUTRAL. flags: home, capital.
# Faction incomes are balanced to 8 per major power.

T = [
    # ── North America ──
    ("alaska",        "Alaska",              "USA",     1, ["__USA_ALASKA__"]),
    ("usa",           "United States",       "USA",     5, ["__USA_MAINLAND__"], "home", "capital"),
    ("canada",        "Canada",              "BRITAIN", 1, ["Canada"]),
    ("greenland",     "Greenland",           None,      1, ["Greenland"]),
    ("mexico",        "Mexico",              None,      2, ["Mexico"]),
    ("central_america","Central America",    None,      1, ["Guatemala", "Belize", "Honduras",
                                                            "El Salvador", "Nicaragua",
                                                            "Costa Rica", "Panama"]),
    ("caribbean",     "Caribbean",           "USA",     1, ["Cuba", "Haiti", "Dominican Rep.",
                                                            "Jamaica", "Bahamas", "Puerto Rico",
                                                            "Trinidad and Tobago"]),
    # ── South America ──
    ("colombia",      "Colombia",            None,      2, ["Colombia"]),
    ("venezuela",     "Venezuela",           None,      2, ["Venezuela"]),
    ("guianas",       "Guianas",             None,      1, ["Guyana", "Suriname", "__FR_GUIANA__"]),
    ("peru",          "Peru & Ecuador",      None,      2, ["Peru", "Ecuador"]),
    ("brazil",        "Brazil",              None,      3, ["Brazil"]),
    ("bolivia",       "Bolivia & Paraguay",  None,      1, ["Bolivia", "Paraguay"]),
    ("chile",         "Chile",               None,      1, ["Chile"]),
    ("argentina",     "Argentina",           None,      2, ["Argentina", "Uruguay"]),
    # ── Europe ──
    ("britain",       "Great Britain",       "BRITAIN", 3, ["United Kingdom"], "home", "capital"),
    ("ireland",       "Ireland",             None,      1, ["Ireland"]),
    ("iceland",       "Iceland",             None,      1, ["Iceland"]),
    ("france",        "France",              None,      3, ["__FR_MAINLAND__"]),
    ("spain",         "Spain & Portugal",    None,      2, ["Spain", "Portugal"]),
    ("low_countries", "Low Countries",       None,      2, ["Belgium", "Netherlands", "Luxembourg"]),
    ("germany",       "Germany",             "GERMANY", 4, ["Germany"], "home", "capital"),
    ("switzerland",   "Switzerland",         None,      1, ["Switzerland"]),
    ("italy",         "Italy",               None,      2, ["Italy"]),
    ("austria_hungary","Austria-Hungary",    None,      2, ["Austria", "Hungary", "Czechia",
                                                            "Slovakia"]),
    ("poland",        "Poland",              "GERMANY", 1, ["Poland"]),
    ("scandinavia",   "Scandinavia",         None,      2, ["Norway", "Sweden", "Denmark"]),
    ("finland",       "Finland",             None,      1, ["Finland"]),
    ("baltic",        "Baltic States",       None,      1, ["Estonia", "Latvia", "Lithuania",
                                                            "Belarus"]),
    ("ukraine",       "Ukraine",             "USSR",    2, ["Ukraine", "Moldova"]),
    ("yugoslavia",    "Yugoslavia",          None,      1, ["Serbia", "Croatia", "Slovenia",
                                                            "Bosnia and Herz.", "Montenegro",
                                                            "Macedonia", "Albania", "Kosovo"]),
    ("romania",       "Romania & Bulgaria",  None,      1, ["Romania", "Bulgaria"]),
    ("greece",        "Greece",              None,      1, ["Greece"]),
    ("turkey",        "Turkey",              None,      2, ["Turkey"]),
    # ── Asia ──
    ("russia",        "Russia",              "USSR",    4, ["Russia"], "home", "capital"),
    ("caucasus",      "Caucasus",            "USSR",    1, ["Georgia", "Armenia", "Azerbaijan"]),
    ("central_asia",  "Central Asia",        "USSR",    1, ["Kazakhstan", "Uzbekistan",
                                                            "Turkmenistan", "Kyrgyzstan",
                                                            "Tajikistan"]),
    ("mongolia",      "Mongolia",            "CHINA",   1, ["Mongolia"]),
    ("china",         "China",               "CHINA",   7, ["China"], "home", "capital"),
    ("korea",         "Korea",               "JAPAN",   2, ["North Korea", "South Korea"]),
    ("japan",         "Japan",               "JAPAN",   5, ["Japan"], "home", "capital"),
    ("taiwan",        "Taiwan",              "JAPAN",   1, ["Taiwan"]),
    ("india",         "India",               "BRITAIN", 2, ["India", "Bangladesh", "Sri Lanka",
                                                            "Nepal", "Bhutan"]),
    ("pakistan",      "Pakistan",            None,      1, ["Pakistan"]),
    ("afghanistan",   "Afghanistan",         None,      1, ["Afghanistan"]),
    ("persia",        "Persia",              None,      2, ["Iran"]),
    ("arabia",        "Arabia",              None,      1, ["Saudi Arabia", "Yemen", "Oman",
                                                            "United Arab Emirates", "Qatar",
                                                            "Kuwait"]),
    ("levant",        "Levant & Iraq",       None,      2, ["Syria", "Iraq", "Jordan", "Lebanon",
                                                            "Israel", "Palestine", "Cyprus",
                                                            "N. Cyprus"]),
    ("burma",         "Burma",               None,      1, ["Myanmar"]),
    ("indochina",     "Indochina",           None,      2, ["Vietnam", "Laos", "Cambodia"]),
    ("siam",          "Siam",                None,      1, ["Thailand"]),
    ("malaya",        "Malaya",              None,      1, ["Malaysia", "Brunei"]),
    ("east_indies",   "East Indies",         None,      2, ["Indonesia", "Timor-Leste"]),
    ("new_guinea",    "New Guinea",          None,      1, ["Papua New Guinea"]),
    ("philippines",   "Philippines",         "USA",     1, ["Philippines"]),
    # ── Oceania ──
    ("australia",     "Australia",           "BRITAIN", 1, ["Australia"]),
    ("new_zealand",   "New Zealand",         None,      1, ["New Zealand"]),
    # ── Africa ──
    ("morocco",       "Morocco",             None,      1, ["Morocco", "W. Sahara"]),
    ("algeria",       "Algeria & Tunisia",   None,      2, ["Algeria", "Tunisia"]),
    ("libya",         "Libya",               None,      1, ["Libya"]),
    ("egypt",         "Egypt",               "BRITAIN", 1, ["Egypt"]),
    ("sudan",         "Sudan",               None,      1, ["Sudan", "S. Sudan"]),
    ("sahara",        "Sahara",              None,      1, ["Mauritania", "Mali", "Niger"]),
    ("west_africa",   "West Africa",         None,      2, ["Senegal", "Gambia", "Guinea",
                                                            "Guinea-Bissau", "Sierra Leone",
                                                            "Liberia", "Côte d'Ivoire", "Ghana",
                                                            "Togo", "Benin", "Burkina Faso"]),
    ("nigeria",       "Nigeria",             None,      2, ["Nigeria"]),
    ("central_africa","Kamerun",             "GERMANY", 1, ["Cameroon", "Chad",
                                                            "Central African Rep."]),
    ("congo",         "Congo",               None,      2, ["Dem. Rep. Congo", "Congo", "Gabon",
                                                            "Eq. Guinea"]),
    ("east_africa",   "East Africa",         None,      1, ["Kenya", "Uganda"]),
    ("german_east_africa", "German East Africa", "GERMANY", 1, ["Tanzania", "Rwanda", "Burundi"]),
    ("horn",          "Horn of Africa",      None,      1, ["Ethiopia", "Somalia", "Somaliland",
                                                            "Eritrea", "Djibouti"]),
    ("angola",        "Angola",              None,      1, ["Angola"]),
    ("rhodesia",      "Rhodesia",            None,      1, ["Zambia", "Zimbabwe"]),
    ("mozambique",    "Mozambique",          None,      1, ["Mozambique", "Malawi"]),
    ("southwest_africa","German S.W. Africa","GERMANY", 1, ["Namibia", "Botswana"]),
    ("south_africa",  "South Africa",        None,      2, ["South Africa", "Lesotho",
                                                            "eSwatini"]),
    ("madagascar",    "Madagascar",          None,      1, ["Madagascar"]),
]

DROPPED_COUNTRIES = {
    "Antarctica", "Fr. S. Antarctic Lands", "Falkland Is.",
    "Fiji", "Vanuatu", "Solomon Is.", "New Caledonia",
}

SEA_LINKS = [
    ("alaska", "russia"),
    ("usa", "caribbean"), ("mexico", "caribbean"), ("caribbean", "venezuela"),
    ("usa", "britain"),
    ("canada", "greenland"), ("greenland", "iceland"),
    ("iceland", "britain"), ("iceland", "scandinavia"),
    ("britain", "france"), ("britain", "scandinavia"), ("britain", "low_countries"),
    ("brazil", "west_africa"),
    ("spain", "morocco"), ("france", "algeria"), ("italy", "libya"),
    ("greece", "levant"),
    ("egypt", "arabia"), ("arabia", "horn"), ("arabia", "persia"),
    ("india", "arabia"),
    ("malaya", "east_indies"), ("east_indies", "australia"),
    ("east_indies", "philippines"), ("philippines", "taiwan"),
    ("taiwan", "china"), ("japan", "taiwan"),
    ("korea", "japan"), ("japan", "russia"),
    ("new_guinea", "australia"), ("australia", "new_zealand"),
    ("madagascar", "mozambique"), ("south_africa", "madagascar"),
]

# Minimum ring area (deg²) — smaller islands are dropped (group's largest
# ring is always kept).
MIN_RING_AREA = 1.2


# ── TopoJSON decoding ─────────────────────────────────────────────────────────

def load_topo():
    topo = json.load(open(SRC, encoding="utf-8"))
    tr = topo["transform"]
    sx, sy = tr["scale"]
    tx, ty = tr["translate"]
    arcs_q = []
    for arc in topo["arcs"]:
        pts, x, y = [], 0, 0
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x, y))
        arcs_q.append(pts)
    geoms = topo["objects"]["countries"]["geometries"]
    to_ll = lambda p: (p[0] * sx + tx, p[1] * sy + ty)
    return arcs_q, geoms, to_ll


def geom_polys(g):
    if g["type"] == "Polygon":
        return [g["arcs"]]
    if g["type"] == "MultiPolygon":
        return g["arcs"]
    return []


def ring_arc_points(arcs_q, signed):
    return arcs_q[signed] if signed >= 0 else list(reversed(arcs_q[~signed]))


def ring_points(arcs_q, ring):
    pts = []
    for s in ring:
        a = ring_arc_points(arcs_q, s)
        if pts and pts[-1] == a[0]:
            pts.extend(a[1:])
        else:
            pts.extend(a)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    return pts


def centroid_ll(arcs_q, ring, to_ll):
    pts = [to_ll(p) for p in ring_points(arcs_q, ring)]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def ring_area_deg2(arcs_q, ring, to_ll):
    pts = [to_ll(p) for p in ring_points(arcs_q, ring)]
    a = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0


# ── country/part → group routing ─────────────────────────────────────────────

def route_part(country, lon, lat):
    """Return pseudo-country name for special multipolygon parts."""
    if country == "United States of America":
        if lon < -140 and lat > 50:
            return "__USA_ALASKA__"
        if lat < 30 and lon < -150:
            return None                      # Hawaii — dropped
        return "__USA_MAINLAND__"
    if country == "France":
        if lat < 20:
            return "__FR_GUIANA__"
        return "__FR_MAINLAND__"
    if country == "Norway" and lat > 74:
        return None                          # Svalbard / Jan Mayen — dropped
    return country


# ── antimeridian handling ─────────────────────────────────────────────────────

def _clip_lon(pts, keep_west: bool, x: float = 180.0):
    """Sutherland-Hodgman clip of a lon/lat ring against the lon=x meridian."""
    inside = (lambda p: p[0] <= x) if keep_west else (lambda p: p[0] >= x)

    def cross(a, b):
        t = (x - a[0]) / (b[0] - a[0])
        return (x, a[1] + (b[1] - a[1]) * t)

    out = []
    for cur, nxt in zip(pts, pts[1:] + pts[:1]):
        if inside(cur):
            out.append(cur)
            if not inside(nxt):
                out.append(cross(cur, nxt))
        elif inside(nxt):
            out.append(cross(cur, nxt))
    return out


def split_antimeridian(pts):
    """Rings spanning the ±180° seam render as a full-width band — split them
    into a western ring (…→180) and an eastern sliver (-180→…)."""
    lons = [p[0] for p in pts]
    if max(lons) - min(lons) <= 300:
        return [pts]
    unwrapped = [(lon + 360 if lon < 0 else lon, lat) for lon, lat in pts]
    west = _clip_lon(unwrapped, keep_west=True)
    east = [(lon - 360, lat) for lon, lat in _clip_lon(unwrapped, keep_west=False)]
    return [r for r in (west, east) if len(r) >= 3]


# ── merge: cancel shared arcs, stitch boundary ───────────────────────────────

def merge_group(arcs_q, member_polys):
    """member_polys: list of polygons (each a list of rings of signed arcs).
    Returns stitched boundary rings as lists of quantized points."""
    usage = defaultdict(int)
    instances = []
    for poly in member_polys:
        for ring in poly:
            for s in ring:
                usage[s if s >= 0 else ~s] += 1
                instances.append(s)

    boundary = [s for s in instances if usage[s if s >= 0 else ~s] == 1]

    # Stitch directed boundary arcs into closed rings
    edges = [ring_arc_points(arcs_q, s) for s in boundary]
    by_start = defaultdict(list)
    for e in edges:
        by_start[e[0]].append(e)

    rings, used = [], set()
    for e in edges:
        if id(e) in used:
            continue
        used.add(id(e))
        ring = list(e)
        while ring[0] != ring[-1]:
            nxt = next((n for n in by_start[ring[-1]] if id(n) not in used), None)
            if nxt is None:
                break  # open chain — degenerate topology
            used.add(id(nxt))
            ring.extend(nxt[1:])
        if len(ring) > 1 and ring[0] == ring[-1]:
            ring.pop()
        if len(ring) >= 3:
            rings.append(ring)
    return rings


# ── main build ────────────────────────────────────────────────────────────────

def build():
    arcs_q, geoms, to_ll = load_topo()

    group_of = {}          # routed country name -> group key
    for entry in T:
        key, _name, _owner, _inc, countries = entry[:5]
        for c in countries:
            group_of[c] = key

    # Collect member polygons per group; track arc→groups for adjacency
    group_polys = defaultdict(list)   # key -> list of polygons (signed-arc rings)
    arc_groups = defaultdict(set)     # abs arc idx -> set of group keys
    unrouted = set()

    for g in geoms:
        cname = g["properties"]["name"]
        if cname in DROPPED_COUNTRIES:
            continue
        for poly in geom_polys(g):
            lon, lat = centroid_ll(arcs_q, poly[0], to_ll)
            routed = route_part(cname, lon, lat)
            if routed is None:
                continue
            key = group_of.get(routed)
            if key is None:
                unrouted.add(routed)
                continue
            group_polys[key].append(poly)
            for ring in poly:
                for s in ring:
                    arc_groups[s if s >= 0 else ~s].add(key)

    if unrouted:
        raise SystemExit(f"UNROUTED countries: {sorted(unrouted)}")
    missing = [e[0] for e in T if e[0] not in group_polys]
    if missing:
        raise SystemExit(f"EMPTY groups: {missing}")

    # Land adjacency from shared arcs
    neighbors = defaultdict(set)
    for groups in arc_groups.values():
        if len(groups) > 1:
            for a in groups:
                for b in groups:
                    if a != b:
                        neighbors[a].add(b)

    # Merge each group's polygons and convert to lon/lat rings
    out_rings = {}
    dropped_rings = 0
    for entry in T:
        key = entry[0]
        rings = merge_group(arcs_q, group_polys[key])
        # area-filter (always keep largest)
        with_area = []
        for r_pts in rings:
            pts = [to_ll(p) for p in r_pts]
            a = 0.0
            for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
                a += x0 * y1 - x1 * y0
            with_area.append((abs(a) / 2.0, pts))
        with_area.sort(key=lambda x: -x[0])
        kept = [with_area[0][1]] + [p for a, p in with_area[1:] if a >= MIN_RING_AREA]
        dropped_rings += len(with_area) - len(kept)
        split = [part for pts in kept for part in split_antimeridian(pts)]
        out_rings[key] = [[(round(lon, 2), round(lat, 2)) for lon, lat in pts]
                          for pts in split]

    # ── emit ──────────────────────────────────────────────────────────────────
    ids = {entry[0]: i for i, entry in enumerate(T)}
    key_links = defaultdict(set)
    for a, b in SEA_LINKS:
        assert a in ids and b in ids, (a, b)
        key_links[a].add(b)
        key_links[b].add(a)

    lines = []
    lines.append('"""')
    lines.append("AUTO-GENERATED by tools/build_territories.py — DO NOT EDIT BY HAND.")
    lines.append("Territory polygons from Natural Earth 110m (world-atlas TopoJSON),")
    lines.append("grouped into game territories; land adjacency derived from shared")
    lines.append("borders, sea links hand-defined in the generator.")
    lines.append('"""')
    lines.append("from game.faction import Faction")
    lines.append("")
    lines.append("TERRITORY_DEFS = [")
    for entry in T:
        key, name, owner, income, _countries = entry[:5]
        flags = entry[5:]
        tid = ids[key]
        owner_s = f"Faction.{owner}" if owner else "Faction.NEUTRAL"
        lines.append(f"    {{   # {tid} — {name}")
        lines.append(f'        "id": {tid}, "name": "{name}",')
        opt = f'        "income": {income}, "owner": {owner_s},'
        if "home" in flags:
            opt += ' "is_home": True,'
        if "capital" in flags:
            opt += ' "capital": True,'
        lines.append(opt)
        lines.append('        "geo_polys": [')
        for ring in out_rings[key]:
            coords = ", ".join(f"({lon},{lat})" for lon, lat in ring)
            lines.append(f"            [{coords}],")
        lines.append("        ],")
        lines.append("    },")
    lines.append("]")
    lines.append("")
    lines.append("ADJACENCY = {")
    for entry in T:
        key = entry[0]
        tid = ids[key]
        nb = sorted(ids[k] for k in neighbors.get(key, ()))
        # a sea link that duplicates a land border is redundant
        sl = sorted(ids[k] for k in key_links.get(key, ())
                    if k not in neighbors.get(key, ()))
        lines.append(f'    {tid}: {{"neighbors": {nb}, "sea_links": {sl}}},  # {entry[1]}')
    lines.append("}")
    lines.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ── report ────────────────────────────────────────────────────────────────
    n_pts = sum(len(r) for rings in out_rings.values() for r in rings)
    n_rings = sum(len(rings) for rings in out_rings.values())
    print(f"territories: {len(T)}   rings: {n_rings} (dropped {dropped_rings} small)"
          f"   points: {n_pts}")

    # connectivity check (BFS over land + sea)
    graph = {ids[e[0]]: set() for e in T}
    for entry in T:
        key = entry[0]
        graph[ids[key]] |= {ids[k] for k in neighbors.get(key, ())}
        graph[ids[key]] |= {ids[k] for k in key_links.get(key, ())}
    seen, stack = {0}, [0]
    while stack:
        for n in graph[stack.pop()]:
            if n not in seen:
                seen.add(n)
                stack.append(n)
    if len(seen) != len(T):
        unreachable = [e[1] for e in T if ids[e[0]] not in seen]
        print(f"WARNING — unreachable territories: {unreachable}")
    else:
        print("graph fully connected")

    # faction summary
    from collections import Counter
    inc = Counter()
    cnt = Counter()
    for entry in T:
        owner = entry[2] or "NEUTRAL"
        inc[owner] += entry[3]
        cnt[owner] += 1
    for f in ("USA", "USSR", "CHINA", "BRITAIN", "GERMANY", "JAPAN", "NEUTRAL"):
        print(f"  {f:8s} territories={cnt[f]:2d} income={inc[f]}")


if __name__ == "__main__":
    build()
