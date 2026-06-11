from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple
from game.faction import Faction


@dataclass
class Territory:
    id: int
    name: str
    # polygon rings in map pixel-space (set after projection); a territory
    # may span several rings (mainland + islands)
    polys: List[list] = field(default_factory=list)
    # geographic rings as (lon, lat) pairs — source of truth for projection
    geo_polys: List[list] = field(default_factory=list)
    # pixel-space bounding boxes per ring (minx, miny, maxx, maxy) for fast hit tests
    bboxes: List[Tuple[int, int, int, int]] = field(default_factory=list)
    # label/badge anchor in pixel space (centroid of the largest ring)
    center: Tuple[int, int] = (0, 0)

    neighbors: List[int] = field(default_factory=list)  # territory IDs
    # sea links allow naval movement between non-adjacent territories
    sea_links: List[int] = field(default_factory=list)

    owner: Faction = Faction.NEUTRAL
    armies: int = 0
    income: int = 1           # gold per turn
    is_home: bool = False     # starting territory for a faction
    capital: bool = False     # losing capital is significant
