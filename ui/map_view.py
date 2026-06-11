"""Renders the world map — territories, borders, labels, army counts."""
from __future__ import annotations
import pygame
from typing import Dict, Optional

from config import (C_OCEAN, C_OCEAN_DEEP, C_BORDER, C_SELECTED, C_WHITE,
                    C_TERRITORY_NEUTRAL, FACTION_COLORS, MAP_RECT)
from game.world import World, _project
from game.territory import Territory
from game.faction import Faction


_LABEL_FONT: Optional[pygame.font.Font] = None
_ARMY_FONT:  Optional[pygame.font.Font] = None
_OCEAN_BG:   Optional[pygame.Surface] = None

# Territories narrower than this (largest ring, px) only show their name
# when hovered or selected — keeps the map uncluttered.
_LABEL_MIN_W = 58


def _fonts():
    global _LABEL_FONT, _ARMY_FONT
    if _LABEL_FONT is None:
        pygame.font.init()
        _LABEL_FONT = pygame.font.SysFont("arial", 10)
        _ARMY_FONT  = pygame.font.SysFont("arial", 11, bold=True)


def _ocean_bg() -> pygame.Surface:
    """Cached ocean background: vertical gradient + subtle graticule."""
    global _OCEAN_BG
    if _OCEAN_BG is not None:
        return _OCEAN_BG
    surf = pygame.Surface(MAP_RECT.size)
    h = MAP_RECT.height
    for row in range(h):
        f = row / max(h - 1, 1)
        col = tuple(int(a + (b - a) * f) for a, b in zip(C_OCEAN, C_OCEAN_DEEP))
        pygame.draw.line(surf, col, (0, row), (MAP_RECT.width, row))

    grid_col = tuple(min(255, c + 12) for c in C_OCEAN_DEEP)
    for lon in range(-150, 181, 30):
        x = _project(lon, 0)[0] - MAP_RECT.x
        pygame.draw.line(surf, grid_col, (x, 0), (x, h))
    for lat in (-30, 0, 30, 60):
        y = _project(0, lat)[1] - MAP_RECT.y
        pygame.draw.line(surf, grid_col, (0, y), (MAP_RECT.width, y))

    _OCEAN_BG = surf
    return surf


def _largest_width(t: Territory) -> int:
    if not t.bboxes:
        return 0
    return max(x1 - x0 for (x0, y0, x1, y1) in t.bboxes)


def draw_map(surface: pygame.Surface, world: World,
             selected: Optional[Territory],
             hovered: Optional[Territory],
             valid_targets: Optional[set] = None,
             override_colors: Optional[Dict[int, tuple]] = None):
    _fonts()

    surface.blit(_ocean_bg(), MAP_RECT.topleft)

    # ── territory fills + borders ─────────────────────────────────────────────
    for t in world.territories.values():
        if override_colors and t.id in override_colors:
            color = override_colors[t.id]
        else:
            base = (C_TERRITORY_NEUTRAL if t.owner == Faction.NEUTRAL
                    else FACTION_COLORS[int(t.owner)])
            color = base
            if t is selected:
                color = _blend(base, C_SELECTED, 0.5)
            elif valid_targets and t.id in valid_targets:
                color = _blend(base, (255, 100, 100), 0.4)
            elif t is hovered:
                color = _lighten(base, 40)

        edge = _blend(color, C_BORDER, 0.55)
        for ring in t.polys:
            if len(ring) < 3:
                continue
            pygame.draw.polygon(surface, color, ring)
            pygame.draw.polygon(surface, edge, ring, 1)

    # Selection ring drawn on top so neighbours don't overpaint it
    if selected:
        for ring in selected.polys:
            if len(ring) >= 3:
                pygame.draw.polygon(surface, C_SELECTED, ring, 2)

    # ── labels & badges ───────────────────────────────────────────────────────
    for t in world.territories.values():
        cx, cy = t.center

        # Army count badge
        badge_surf = _ARMY_FONT.render(str(t.armies), True, C_WHITE)
        bw, bh = badge_surf.get_size()
        bg_surf = pygame.Surface((bw + 6, bh + 2), pygame.SRCALPHA)
        pygame.draw.rect(bg_surf, (0, 0, 0, 150), bg_surf.get_rect(),
                         border_radius=4)
        surface.blit(bg_surf, (cx - bw // 2 - 3, cy - bh // 2 - 1))
        surface.blit(badge_surf, (cx - bw // 2, cy - bh // 2))

        # Territory name — only when there is room, or on interaction
        if (_largest_width(t) >= _LABEL_MIN_W
                or t is hovered or t is selected):
            name_surf = _LABEL_FONT.render(t.name, True, C_WHITE)
            shadow = _LABEL_FONT.render(t.name, True, (0, 0, 0))
            nw = name_surf.get_width()
            nx, ny = cx - nw // 2, cy + bh // 2 + 2
            surface.blit(shadow, (nx + 1, ny + 1))
            surface.blit(name_surf, (nx, ny))


def _lighten(color: tuple, amount: int) -> tuple:
    return tuple(min(255, c + amount) for c in color)


def _blend(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(ac * (1 - t) + bc * t) for ac, bc in zip(a, b))
