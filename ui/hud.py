"""HUD — top bar (turn/phase) and bottom panel (territory info + action buttons)."""
from __future__ import annotations
import pygame
from typing import Optional, List

from config import (SCREEN_W,
                    TOP_BAR_RECT, BOTTOM_BAR_RECT,
                    C_PANEL, C_PANEL_LIGHT, C_TEXT, C_GOLD, C_WHITE, C_GREEN,
                    C_BUTTON, C_BUTTON_HOV, C_BUTTON_DIS,
                    FACTION_COLORS, FACTION_NAMES,
                    PHASE_PURCHASE)
from game.territory import Territory
from game.player import Player
from game.faction import Faction


_FONTS: dict = {}


def _font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _FONTS:
        _FONTS[key] = pygame.font.SysFont("arial", size, bold=bold)
    return _FONTS[key]


class Button:
    def __init__(self, rect: pygame.Rect, label: str, action: str, enabled: bool = True):
        self.rect = rect
        self.label = label
        self.action = action
        self.enabled = enabled
        self._hovered = False

    def draw(self, surface: pygame.Surface):
        if not self.enabled:
            color = C_BUTTON_DIS
        elif self._hovered:
            color = C_BUTTON_HOV
        else:
            color = C_BUTTON
        pygame.draw.rect(surface, color, self.rect, border_radius=4)
        pygame.draw.rect(surface, C_WHITE, self.rect, 1, border_radius=4)
        f = _font(12, bold=True)
        txt = f.render(self.label, True, C_WHITE if self.enabled else (100, 100, 100))
        surface.blit(txt, txt.get_rect(center=self.rect.center))

    def handle_motion(self, pos):
        self._hovered = self.rect.collidepoint(pos) and self.enabled

    def handle_click(self, pos) -> Optional[str]:
        if self.rect.collidepoint(pos) and self.enabled:
            return self.action
        return None


class HUD:
    def __init__(self):
        self.buttons: List[Button] = []
        self._build_buttons()

    def _build_buttons(self):
        bx = BOTTOM_BAR_RECT.x + 10
        by = BOTTOM_BAR_RECT.y + 10
        bw, bh = 110, 32
        gap = 8
        defs = [
            ("Buy Armies",  "buy_army"),
            ("End Turn",    "end_turn"),
        ]
        for label, action in defs:
            self.buttons.append(Button(pygame.Rect(bx, by, bw, bh), label, action))
            bx += bw + gap

    def update_buttons(self, phase: str, player: Player):
        enabled_map = {
            "buy_army":    phase == PHASE_PURCHASE and player.can_buy_army(),
            "end_turn":    True,
        }
        for btn in self.buttons:
            btn.enabled = enabled_map.get(btn.action, False)

    def draw(self, surface: pygame.Surface,
             turn: int, phase: str,
             player: Player, all_players: List[Player],
             selected: Optional[Territory],
             message: str = ""):
        # Top bar
        pygame.draw.rect(surface, C_PANEL, TOP_BAR_RECT)
        pygame.draw.line(surface, C_PANEL_LIGHT,
                         TOP_BAR_RECT.bottomleft, TOP_BAR_RECT.bottomright)

        f_small = _font(12)
        f_med   = _font(13, bold=True)

        # Turn number
        turn_txt = f_med.render(f"Turn {turn}", True, C_GOLD)
        surface.blit(turn_txt, (10, 10))

        # Phase
        phase_txt = f_small.render(f"Phase: {phase.upper()}", True, C_TEXT)
        surface.blit(phase_txt, (100, 11))

        # Player scoreboard
        px = 260
        for p in all_players:
            if p.faction == Faction.NEUTRAL:
                continue
            col = FACTION_COLORS[int(p.faction)]
            label = f"{FACTION_NAMES[int(p.faction)]}: ${p.gold}"
            is_current = p is player
            fc = C_WHITE if is_current else C_TEXT
            if not p.alive:
                fc = (80, 80, 80)
            txt = f_small.render(label, True, fc)
            if is_current:
                pygame.draw.rect(surface, col,
                                 pygame.Rect(px - 3, 5, txt.get_width() + 6, 26),
                                 border_radius=3)
            surface.blit(txt, (px, 11))
            px += txt.get_width() + 20

        # Message line
        if message:
            msg_txt = f_small.render(message, True, C_GOLD)
            surface.blit(msg_txt, (SCREEN_W - msg_txt.get_width() - 10, 11))

        # Bottom panel
        pygame.draw.rect(surface, C_PANEL, BOTTOM_BAR_RECT)
        pygame.draw.line(surface, C_PANEL_LIGHT,
                         BOTTOM_BAR_RECT.topleft, BOTTOM_BAR_RECT.topright)

        # Selected territory info
        if selected:
            ix = BOTTOM_BAR_RECT.x + 640
            iy = BOTTOM_BAR_RECT.y + 8
            owner_col = FACTION_COLORS[int(selected.owner)]
            owner_name = FACTION_NAMES[int(selected.owner)]
            lines = [
                (f"{selected.name}", C_WHITE, True),
                (f"Owner: {owner_name}", owner_col, False),
                (f"Armies: {selected.armies}  Income: ${selected.income}", C_TEXT, False),
            ]
            for line, color, bold in lines:
                surf = _font(12, bold).render(line, True, color)
                surface.blit(surf, (ix, iy))
                iy += 18

        # Reinforcement status / purchase help
        if phase == PHASE_PURCHASE:
            available = player.pending_armies + player.affordable_armies()
            if available > 0:
                pa_txt = f_med.render(
                    f"Armies to place: {available}", True, C_GREEN)
                surface.blit(pa_txt,
                             (BOTTOM_BAR_RECT.x + 640, BOTTOM_BAR_RECT.y + 70))
                tip = _font(11).render(
                    "Click your territory to place  ·  Shift: ×5  ·  Ctrl: all",
                    True, C_TEXT)
                surface.blit(tip,
                             (BOTTOM_BAR_RECT.x + 640, BOTTOM_BAR_RECT.y + 90))
        elif player.pending_armies > 0:
            pa_txt = f_med.render(
                f"Armies to place: {player.pending_armies}", True, C_GREEN)
            surface.blit(pa_txt, (BOTTOM_BAR_RECT.x + 640, BOTTOM_BAR_RECT.y + 70))

        # Map navigation hint
        hint = _font(10).render(
            "Mouse wheel: zoom  ·  Drag: pan  ·  R: reset view",
            True, (110, 115, 125))
        surface.blit(hint, (BOTTOM_BAR_RECT.x + 10, BOTTOM_BAR_RECT.bottom - 20))

        # Draw buttons
        for btn in self.buttons:
            btn.draw(surface)

    def handle_motion(self, pos):
        for btn in self.buttons:
            btn.handle_motion(pos)

    def handle_click(self, pos) -> Optional[str]:
        for btn in self.buttons:
            result = btn.handle_click(pos)
            if result:
                return result
        return None
