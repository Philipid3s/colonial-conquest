"""World — builds territories and handles projection from geo coords to pixels."""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import math

from config import (MAP_RECT, MAP_LON_MIN, MAP_LON_MAX, MAP_LAT_MIN, MAP_LAT_MAX,
                    NEUTRAL_ARMIES, STARTING_ARMIES)
from game.faction import Faction
from game.territory import Territory
from data.territories import TERRITORY_DEFS, ADJACENCY


# ── Miller cylindrical projection ─────────────────────────────────────────────
# Better shape fidelity than equirectangular: mid-latitude countries (Europe,
# USA, China) look far more proportional; polar distortion is still present
# but much less severe than Mercator.
#
# Formula:  y_miller = 5/4 · ln( tan(π/4 + 2φ/5) )   where φ = lat in radians

def _miller_y(lat_deg: float) -> float:
    φ = math.radians(lat_deg)
    return 5 / 4 * math.log(math.tan(math.pi / 4 + 2 * φ / 5))

_M_TOP = _miller_y(MAP_LAT_MAX)          # Miller y at lat = +85°
_M_BOT = _miller_y(MAP_LAT_MIN)          # Miller y at lat = -60°
_M_RNG = _M_TOP - _M_BOT


def _project(lon: float, lat: float) -> Tuple[int, int]:
    """Miller cylindrical projection from (lon, lat) to map pixel coords."""
    lat = max(MAP_LAT_MIN, min(MAP_LAT_MAX, lat))
    x = MAP_RECT.x + int((lon - MAP_LON_MIN) / (MAP_LON_MAX - MAP_LON_MIN)
                         * MAP_RECT.width)
    y = MAP_RECT.y + int((_M_TOP - _miller_y(lat)) / _M_RNG * MAP_RECT.height)
    return (x, y)


def _poly_centroid(pts: List[Tuple[int, int]]) -> Tuple[int, int]:
    """Area-weighted (shoelace) centroid — robust for concave shapes."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(a) < 1e-9:
        return pts[0]
    return (int(cx / (3 * a)), int(cy / (3 * a)))


def _poly_area(pts: List[Tuple[int, int]]) -> float:
    a = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0


class World:
    def __init__(self):
        self.territories: Dict[int, Territory] = {}
        self._build()

    def _build(self):
        # Build Territory objects
        for d in TERRITORY_DEFS:
            t = Territory(
                id=d["id"],
                name=d["name"],
                income=d.get("income", 1),
                owner=d.get("owner", Faction.NEUTRAL),
                is_home=d.get("is_home", False),
                capital=d.get("capital", False),
                geo_polys=d["geo_polys"],
            )
            t.polys = [[_project(lon, lat) for lon, lat in ring]
                       for ring in t.geo_polys]
            t.bboxes = []
            for ring in t.polys:
                xs = [p[0] for p in ring]
                ys = [p[1] for p in ring]
                t.bboxes.append((min(xs), min(ys), max(xs), max(ys)))
            largest = max(t.polys, key=_poly_area)
            t.center = _poly_centroid(largest)
            # Default garrisons: richer neutrals defend harder
            if t.owner == Faction.NEUTRAL:
                t.armies = NEUTRAL_ARMIES + t.income
            self.territories[t.id] = t

        # Wire adjacency
        for tid, adj in ADJACENCY.items():
            t = self.territories[tid]
            t.neighbors = adj.get("neighbors", [])
            t.sea_links = adj.get("sea_links", [])

    def place_starting_armies(self, players):
        """Distribute starting armies into each faction's home territories."""
        for player in players:
            if player.faction == Faction.NEUTRAL:
                continue
            homes = [t for t in self.territories.values()
                     if t.owner == player.faction]
            if not homes:
                continue
            per_territory = max(1, STARTING_ARMIES // len(homes))
            remainder = STARTING_ARMIES - per_territory * len(homes)
            for t in homes:
                t.armies = per_territory
            # give remainder to capital or first territory
            capital = next((t for t in homes if t.capital), homes[0])
            capital.armies += max(0, remainder)

    def territory_at(self, screen_pos: Tuple[int, int]) -> Optional[Territory]:
        """Return the territory whose polygon contains screen_pos."""
        x, y = screen_pos
        for t in self.territories.values():
            for (x0, y0, x1, y1), ring in zip(t.bboxes, t.polys):
                if (x0 <= x <= x1 and y0 <= y <= y1 and len(ring) >= 3
                        and _point_in_poly(screen_pos, ring)):
                    return t
        return None

    def owned_by(self, faction: Faction) -> List[Territory]:
        return [t for t in self.territories.values() if t.owner == faction]

    def total_territories(self) -> int:
        return len(self.territories)

    def check_victory(self, faction: Faction) -> bool:
        from config import VICTORY_THRESHOLD
        owned = len(self.owned_by(faction))
        return owned / self.total_territories() >= VICTORY_THRESHOLD


def _point_in_poly(point: Tuple[int, int], poly: List[Tuple[int, int]]) -> bool:
    """Ray-casting algorithm for point-in-polygon."""
    x, y = point
    inside = False
    px, py = poly[-1]
    for cx, cy in poly:
        if ((cy > y) != (py > y)) and (x < (px - cx) * (y - cy) / (py - cy) + cx):
            inside = not inside
        px, py = cx, cy
    return inside
