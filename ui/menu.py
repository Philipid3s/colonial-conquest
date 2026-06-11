"""Start menu — title screen with faction selection."""
from __future__ import annotations
import sys
import pygame
from typing import Optional

from config import (SCREEN_W, SCREEN_H, C_BG, C_WHITE, C_GOLD,
                    FACTION_COLORS, FACTION_NAMES)
from game.faction import Faction
from game.world import World
from ui.map_view import draw_map


# Short taglines shown on each faction button
_TAGLINES = {
    Faction.USA:     "North American superpower",
    Faction.USSR:    "Soviet industrial giant",
    Faction.CHINA:   "The world's largest nation",
    Faction.BRITAIN: "Global maritime empire",
    Faction.GERMANY: "Heart of Europe",
    Faction.JAPAN:   "Pacific island empire",
}

_FACTION_ORDER = [
    Faction.USA, Faction.USSR, Faction.CHINA,
    Faction.BRITAIN, Faction.GERMANY, Faction.JAPAN,
]


def _font(size: int, bold: bool = False) -> pygame.font.Font:
    return pygame.font.SysFont("arial", size, bold=bold)


# ── Faction button ─────────────────────────────────────────────────────────────

class _FactionButton:
    W, H = 192, 88

    def __init__(self, rect: pygame.Rect, faction: Faction):
        self.rect = rect
        self.faction = faction
        self.hovered = False

    def draw(self, surface: pygame.Surface, selected: bool):
        color = FACTION_COLORS[int(self.faction)]
        active = selected or self.hovered

        # Filled background
        bg = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
        bg.fill((*color, 200 if active else 80))
        surface.blit(bg, self.rect.topleft)

        # Border
        border_col = C_GOLD if selected else (C_WHITE if self.hovered else
                                              tuple(min(255, c + 40) for c in color))
        pygame.draw.rect(surface, border_col, self.rect,
                         3 if selected else 1, border_radius=6)

        # Faction name
        name_surf = _font(15, bold=True).render(
            FACTION_NAMES[int(self.faction)], True, C_WHITE)
        surface.blit(name_surf,
                     name_surf.get_rect(centerx=self.rect.centerx,
                                        y=self.rect.y + 18))

        # Tagline
        tag_surf = _font(10).render(_TAGLINES[self.faction], True,
                                    (210, 210, 200))
        surface.blit(tag_surf,
                     tag_surf.get_rect(centerx=self.rect.centerx,
                                       y=self.rect.y + 44))

        # Color stripe at bottom
        stripe = pygame.Rect(self.rect.x + 1,
                             self.rect.bottom - 10,
                             self.rect.w - 2, 9)
        pygame.draw.rect(surface, color, stripe,
                         border_radius=4)

    def handle_motion(self, pos: tuple):
        self.hovered = self.rect.collidepoint(pos)

    def hit(self, pos: tuple) -> bool:
        return self.rect.collidepoint(pos)


# ── Start menu ─────────────────────────────────────────────────────────────────

class StartMenu:
    """Renders the title screen and returns the faction the player chose."""

    def __init__(self, screen: pygame.Surface, world: World):
        self.screen = screen
        self.world = world
        self.selected: Faction = Faction.USA
        self._buttons: list[_FactionButton] = []
        self._start_rect = pygame.Rect(0, 0, 0, 0)
        self._start_hovered = False
        self._hovered_faction: Optional[Faction] = None

        # Pre-render base map and dark overlay (expensive — do once)
        self._base_map = pygame.Surface((SCREEN_W, SCREEN_H))
        self._base_map.fill(C_BG)
        draw_map(self._base_map, world, None, None, None)

        self._overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self._overlay.fill((6, 10, 20, 200))

        self._build_layout()

    def _build_layout(self):
        cols, rows = 3, 2
        bw, bh = _FactionButton.W, _FactionButton.H
        gap_x, gap_y = 20, 16
        grid_w = cols * bw + (cols - 1) * gap_x
        grid_h = rows * bh + (rows - 1) * gap_y

        x0 = (SCREEN_W - grid_w) // 2
        y0 = 260  # below title + subtitle

        for i, faction in enumerate(_FACTION_ORDER):
            col, row = i % cols, i // cols
            rect = pygame.Rect(x0 + col * (bw + gap_x),
                               y0 + row * (bh + gap_y),
                               bw, bh)
            self._buttons.append(_FactionButton(rect, faction))

        # Start button centred below the grid
        btn_w, btn_h = 240, 52
        self._start_rect = pygame.Rect((SCREEN_W - btn_w) // 2,
                                       y0 + grid_h + 44,
                                       btn_w, btn_h)

    # ── public ────────────────────────────────────────────────────────────────

    def run(self) -> Faction:
        """Block until the player clicks Start; return the chosen Faction."""
        pygame.font.init()
        clock = pygame.time.Clock()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                elif event.type == pygame.MOUSEMOTION:
                    self._hovered_faction = None
                    for btn in self._buttons:
                        btn.handle_motion(event.pos)
                        if btn.hovered:
                            self._hovered_faction = btn.faction
                    self._start_hovered = self._start_rect.collidepoint(event.pos)

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for btn in self._buttons:
                        if btn.hit(event.pos):
                            self.selected = btn.faction
                    if self._start_rect.collidepoint(event.pos):
                        return self.selected

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        return self.selected
                    elif event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()

            self._draw()
            clock.tick(60)

    # ── rendering ─────────────────────────────────────────────────────────────

    def _draw(self):
        # 1 — dim world map base
        self.screen.blit(self._base_map, (0, 0))
        self.screen.blit(self._overlay, (0, 0))

        # 2 — glow the highlighted faction's territories through the overlay
        focus = self._hovered_faction if self._hovered_faction else self.selected
        self._draw_faction_glow(focus)

        # 3 — title
        self._draw_title()

        # 4 — faction buttons
        for btn in self._buttons:
            btn.draw(self.screen, btn.faction == self.selected)

        # 5 — start button
        self._draw_start_button()

        # 6 — hint text
        hint = _font(11).render(
            "Click a faction to select  ·  ENTER or click Start to begin",
            True, (120, 120, 110))
        self.screen.blit(
            hint, hint.get_rect(centerx=SCREEN_W // 2,
                                 y=self._start_rect.bottom + 18))

        pygame.display.flip()

    def _draw_faction_glow(self, faction: Faction):
        """Re-draw a faction's territories bright so they glow through the overlay."""
        base = FACTION_COLORS[int(faction)]
        bright = tuple(min(255, c + 90) for c in base)
        for t in self.world.territories.values():
            if t.owner != faction:
                continue
            for ring in t.polys:
                if len(ring) >= 3:
                    pygame.draw.polygon(self.screen, bright, ring)
                    pygame.draw.polygon(self.screen, (0, 0, 0), ring, 1)

    def _draw_title(self):
        title = _font(52, bold=True).render("COLONIAL CONQUEST", True, C_GOLD)
        self.screen.blit(title,
                         title.get_rect(centerx=SCREEN_W // 2, y=80))

        year = _font(13).render(
            "World Domination  ·  Choose your superpower", True, (160, 150, 120))
        self.screen.blit(year,
                         year.get_rect(centerx=SCREEN_W // 2, y=152))

        # Thin gold divider
        pygame.draw.line(self.screen, C_GOLD,
                         (SCREEN_W // 2 - 220, 178),
                         (SCREEN_W // 2 + 220, 178), 1)

    def _draw_start_button(self):
        r = self._start_rect
        color = (55, 130, 55) if self._start_hovered else (35, 95, 35)
        pygame.draw.rect(self.screen, color, r, border_radius=8)
        pygame.draw.rect(self.screen,
                         C_GOLD if self._start_hovered else (180, 160, 50),
                         r, 2, border_radius=8)

        label = _font(17, bold=True).render("START CAMPAIGN", True, C_WHITE)
        self.screen.blit(label, label.get_rect(center=r.center))
