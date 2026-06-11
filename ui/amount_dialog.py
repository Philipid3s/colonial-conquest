"""Modal dialog for choosing an army amount (move / attack commitment)."""
from __future__ import annotations
import sys
import pygame
from typing import Optional

from config import (SCREEN_W, SCREEN_H, C_PANEL, C_PANEL_LIGHT, C_GOLD,
                    C_WHITE, C_TEXT, C_BUTTON, C_BUTTON_HOV, C_GREEN, C_RED)


def _font(size: int, bold: bool = False) -> pygame.font.Font:
    return pygame.font.SysFont("arial", size, bold=bold)


class AmountDialog:
    """Blocking modal: pick an integer in [1, max_amount].

    Controls: slider drag/click, +/− buttons, mouse wheel,
    ←/→ ±1, ↑/↓ ±5, HOME/END, ENTER confirm, ESC cancel.
    Returns the chosen amount, or None if cancelled.
    """
    W, H = 420, 190

    def __init__(self, screen: pygame.Surface):
        self.screen = screen

    def run(self, title: str, max_amount: int,
            default: Optional[int] = None) -> Optional[int]:
        if max_amount < 1:
            return None
        if max_amount == 1:
            return 1

        value = max_amount if default is None else max(1, min(default, max_amount))
        backdrop = self.screen.copy()
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 130))

        panel = pygame.Rect(0, 0, self.W, self.H)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)

        slider = pygame.Rect(panel.x + 60, panel.y + 96, self.W - 120, 8)
        minus_btn = pygame.Rect(panel.x + 22, slider.y - 8, 26, 24)
        plus_btn = pygame.Rect(panel.right - 48, slider.y - 8, 26, 24)
        ok_btn = pygame.Rect(panel.centerx + 12, panel.bottom - 48, 110, 32)
        cancel_btn = pygame.Rect(panel.centerx - 122, panel.bottom - 48, 110, 32)

        dragging = False
        clock = pygame.time.Clock()

        def value_from_x(mx: int) -> int:
            t = (mx - slider.x) / max(slider.width, 1)
            return max(1, min(max_amount, round(1 + t * (max_amount - 1))))

        while True:
            mouse = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return None
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        return value
                    if event.key == pygame.K_LEFT:
                        value = max(1, value - 1)
                    elif event.key == pygame.K_RIGHT:
                        value = min(max_amount, value + 1)
                    elif event.key == pygame.K_DOWN:
                        value = max(1, value - 5)
                    elif event.key == pygame.K_UP:
                        value = min(max_amount, value + 5)
                    elif event.key == pygame.K_HOME:
                        value = 1
                    elif event.key == pygame.K_END:
                        value = max_amount

                elif event.type == pygame.MOUSEWHEEL:
                    value = max(1, min(max_amount, value + event.y))

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if ok_btn.collidepoint(event.pos):
                        return value
                    if cancel_btn.collidepoint(event.pos):
                        return None
                    if minus_btn.collidepoint(event.pos):
                        value = max(1, value - 1)
                    elif plus_btn.collidepoint(event.pos):
                        value = min(max_amount, value + 1)
                    elif slider.inflate(0, 16).collidepoint(event.pos):
                        dragging = True
                        value = value_from_x(event.pos[0])
                    elif not panel.collidepoint(event.pos):
                        return None  # click outside cancels

                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    dragging = False

                elif event.type == pygame.MOUSEMOTION and dragging:
                    value = value_from_x(event.pos[0])

            self._draw(backdrop, dim, panel, slider, minus_btn, plus_btn,
                       ok_btn, cancel_btn, title, value, max_amount, mouse)
            clock.tick(60)

    # ── rendering ─────────────────────────────────────────────────────────────

    def _draw(self, backdrop, dim, panel, slider, minus_btn, plus_btn,
              ok_btn, cancel_btn, title, value, max_amount, mouse):
        self.screen.blit(backdrop, (0, 0))
        self.screen.blit(dim, (0, 0))

        pygame.draw.rect(self.screen, C_PANEL, panel, border_radius=8)
        pygame.draw.rect(self.screen, C_GOLD, panel, 2, border_radius=8)

        t_surf = _font(15, bold=True).render(title, True, C_WHITE)
        self.screen.blit(t_surf, t_surf.get_rect(centerx=panel.centerx,
                                                 y=panel.y + 14))

        # Value readout
        v_surf = _font(26, bold=True).render(str(value), True, C_GOLD)
        self.screen.blit(v_surf, v_surf.get_rect(centerx=panel.centerx,
                                                 y=panel.y + 42))
        rng = _font(11).render(f"of {max_amount}", True, C_TEXT)
        self.screen.blit(rng, rng.get_rect(centerx=panel.centerx,
                                           y=panel.y + 74))

        # Slider track + fill + handle
        pygame.draw.rect(self.screen, C_PANEL_LIGHT, slider, border_radius=4)
        t = (value - 1) / max(max_amount - 1, 1)
        fill = pygame.Rect(slider.x, slider.y, int(slider.width * t), slider.height)
        pygame.draw.rect(self.screen, C_GOLD, fill, border_radius=4)
        hx = slider.x + int(slider.width * t)
        pygame.draw.circle(self.screen, C_WHITE, (hx, slider.centery), 8)

        # +/- buttons
        for rect, label in ((minus_btn, "−"), (plus_btn, "+")):
            col = C_BUTTON_HOV if rect.collidepoint(mouse) else C_BUTTON
            pygame.draw.rect(self.screen, col, rect, border_radius=4)
            s = _font(15, bold=True).render(label, True, C_WHITE)
            self.screen.blit(s, s.get_rect(center=rect.center))

        # OK / Cancel
        for rect, label, base in ((ok_btn, "CONFIRM", C_GREEN),
                                  (cancel_btn, "CANCEL", C_RED)):
            col = tuple(min(255, c + 30) for c in base) \
                if rect.collidepoint(mouse) else base
            pygame.draw.rect(self.screen, col, rect, border_radius=5)
            s = _font(13, bold=True).render(label, True, C_WHITE)
            self.screen.blit(s, s.get_rect(center=rect.center))

        pygame.display.flip()
