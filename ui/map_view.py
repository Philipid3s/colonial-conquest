"""Renders the world map — territories, borders, labels, army counts."""
from __future__ import annotations
import pygame
from typing import Dict, Optional

from config import (C_OCEAN, C_OCEAN_DEEP, C_BORDER, C_SELECTED, C_WHITE,
                    C_TERRITORY_NEUTRAL, FACTION_COLORS, MAP_RECT)
from game.world import World, _project
from game.territory import Territory
from game.faction import Faction
from ui.camera import Camera


_LABEL_FONT: Optional[pygame.font.Font] = None
_ARMY_FONT:  Optional[pygame.font.Font] = None
_OCEAN_BG:   Optional[pygame.Surface] = None

# Territories narrower than this on screen only show their name when hovered
# or selected — zooming in naturally reveals more labels.
_LABEL_MIN_W = 58

# Transformed-geometry cache: rebuilt when the camera changes
_XF = {"key": None, "polys": {}, "centers": {}, "bboxes": {}}


def _fonts():
    global _LABEL_FONT, _ARMY_FONT
    if _LABEL_FONT is None:
        pygame.font.init()
        _LABEL_FONT = pygame.font.SysFont("arial", 10)
        _ARMY_FONT  = pygame.font.SysFont("arial", 11, bold=True)


def _ocean_bg() -> pygame.Surface:
    """Cached ocean background (vertical gradient)."""
    global _OCEAN_BG
    if _OCEAN_BG is not None:
        return _OCEAN_BG
    surf = pygame.Surface(MAP_RECT.size)
    h = MAP_RECT.height
    for row in range(h):
        f = row / max(h - 1, 1)
        col = tuple(int(a + (b - a) * f) for a, b in zip(C_OCEAN, C_OCEAN_DEEP))
        pygame.draw.line(surf, col, (0, row), (MAP_RECT.width, row))
    _OCEAN_BG = surf
    return surf


def _draw_graticule(surface: pygame.Surface, camera: Optional[Camera]):
    grid_col = tuple(min(255, c + 12) for c in C_OCEAN_DEEP)
    xf = camera.world_to_screen if camera else (lambda p: p)
    for lon in range(-150, 181, 30):
        x = xf(_project(lon, 0))[0]
        if MAP_RECT.left <= x <= MAP_RECT.right:
            pygame.draw.line(surface, grid_col,
                             (x, MAP_RECT.top), (x, MAP_RECT.bottom))
    for lat in (-30, 0, 30, 60):
        y = xf(_project(0, lat))[1]
        if MAP_RECT.top <= y <= MAP_RECT.bottom:
            pygame.draw.line(surface, grid_col,
                             (MAP_RECT.left, y), (MAP_RECT.right, y))


def _geometry(world: World, camera: Optional[Camera], t: Territory):
    """Screen-space (rings, bboxes, center) for a territory under the camera."""
    if camera is None or camera.is_identity:
        return t.polys, t.bboxes, t.center

    key = (id(world), camera.version)
    if _XF["key"] != key:
        _XF["key"] = key
        _XF["polys"].clear()
        _XF["centers"].clear()
        _XF["bboxes"].clear()
    if t.id not in _XF["polys"]:
        # cull in world space before transforming
        vx0, vy0, vx1, vy1 = camera.viewport_world()
        rings, boxes = [], []
        for ring, (x0, y0, x1, y1) in zip(t.polys, t.bboxes):
            if x1 < vx0 or x0 > vx1 or y1 < vy0 or y0 > vy1:
                continue
            xf_ring = [camera.world_to_screen(p) for p in ring]
            rings.append(xf_ring)
            boxes.append((camera.world_to_screen((x0, y0)),
                          camera.world_to_screen((x1, y1))))
        _XF["polys"][t.id] = rings
        _XF["bboxes"][t.id] = [(a[0], a[1], b[0], b[1]) for a, b in boxes]
        _XF["centers"][t.id] = camera.world_to_screen(t.center)
    return _XF["polys"][t.id], _XF["bboxes"][t.id], _XF["centers"][t.id]


def _largest_width(bboxes) -> int:
    if not bboxes:
        return 0
    return max(x1 - x0 for (x0, y0, x1, y1) in bboxes)


def draw_map(surface: pygame.Surface, world: World,
             selected: Optional[Territory],
             hovered: Optional[Territory],
             valid_targets: Optional[set] = None,
             override_colors: Optional[Dict[int, tuple]] = None,
             camera: Optional[Camera] = None):
    _fonts()

    prev_clip = surface.get_clip()
    surface.set_clip(MAP_RECT)
    surface.blit(_ocean_bg(), MAP_RECT.topleft)
    _draw_graticule(surface, camera)

    visible = []   # (territory, rings, bboxes, center)
    for t in world.territories.values():
        rings, bboxes, center = _geometry(world, camera, t)
        if not rings:
            continue
        visible.append((t, rings, bboxes, center))

    # ── territory fills + borders ─────────────────────────────────────────────
    for t, rings, _bb, _c in visible:
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
        for ring in rings:
            if len(ring) < 3:
                continue
            pygame.draw.polygon(surface, color, ring)
            pygame.draw.polygon(surface, edge, ring, 1)

    # Selection ring drawn on top so neighbours don't overpaint it
    if selected:
        sel_rings, _, _ = _geometry(world, camera, selected)
        for ring in sel_rings:
            if len(ring) >= 3:
                pygame.draw.polygon(surface, C_SELECTED, ring, 2)

    # ── labels & badges ───────────────────────────────────────────────────────
    for t, _rings, bboxes, (cx, cy) in visible:
        if not MAP_RECT.collidepoint((cx, cy)):
            continue

        # Army count badge
        badge_surf = _ARMY_FONT.render(str(t.armies), True, C_WHITE)
        bw, bh = badge_surf.get_size()
        bg_surf = pygame.Surface((bw + 6, bh + 2), pygame.SRCALPHA)
        pygame.draw.rect(bg_surf, (0, 0, 0, 150), bg_surf.get_rect(),
                         border_radius=4)
        surface.blit(bg_surf, (cx - bw // 2 - 3, cy - bh // 2 - 1))
        surface.blit(badge_surf, (cx - bw // 2, cy - bh // 2))

        # Territory name — only when there is room, or on interaction
        if (_largest_width(bboxes) >= _LABEL_MIN_W
                or t is hovered or t is selected):
            name_surf = _LABEL_FONT.render(t.name, True, C_WHITE)
            shadow = _LABEL_FONT.render(t.name, True, (0, 0, 0))
            nw = name_surf.get_width()
            nx, ny = cx - nw // 2, cy + bh // 2 + 2
            surface.blit(shadow, (nx + 1, ny + 1))
            surface.blit(name_surf, (nx, ny))

    surface.set_clip(prev_clip)


def _lighten(color: tuple, amount: int) -> tuple:
    return tuple(min(255, c + amount) for c in color)


def _blend(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(ac * (1 - t) + bc * t) for ac, bc in zip(a, b))
