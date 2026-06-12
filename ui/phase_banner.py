"""Transient turn/phase announcement — a strip that slides in, holds, fades."""
from __future__ import annotations
import pygame
from typing import Optional

from config import MAP_RECT, C_TEXT

_SLIDE_MS = 260
_HOLD_MS  = 950
_FADE_MS  = 380


class PhaseBanner:
    """Non-blocking overlay banner. show() arms it; draw() renders the
    current animation frame each game frame until the banner expires."""

    def __init__(self):
        self._title = ""
        self._sub = ""
        self._color = (220, 180, 50)
        self._start: Optional[int] = None
        self._fonts: dict = {}

    def _font(self, size: int) -> pygame.font.Font:
        if size not in self._fonts:
            self._fonts[size] = pygame.font.SysFont("arial", size, bold=True)
        return self._fonts[size]

    def show(self, title: str, sub: str = "", color=(220, 180, 50)):
        self._title = title
        self._sub = sub
        self._color = color
        self._start = pygame.time.get_ticks()

    def draw(self, surface: pygame.Surface):
        if self._start is None:
            return
        t = pygame.time.get_ticks() - self._start
        if t >= _SLIDE_MS + _HOLD_MS + _FADE_MS:
            self._start = None
            return

        if t < _SLIDE_MS:
            p = t / _SLIDE_MS
            ease = 1.0 - (1.0 - p) ** 3
            alpha = int(255 * p)
            slide = int(90 * (1.0 - ease))   # title from the left, sub from the right
            lift = 0
        elif t < _SLIDE_MS + _HOLD_MS:
            alpha, slide, lift = 255, 0, 0
        else:
            p = (t - _SLIDE_MS - _HOLD_MS) / _FADE_MS
            alpha = int(255 * (1.0 - p))
            slide = 0
            lift = int(18 * p * p)           # drift upward while fading

        cx = MAP_RECT.centerx
        cy = MAP_RECT.top + 150 - lift

        title_s = self._font(38).render(self._title, True, self._color)
        shadow_s = self._font(38).render(self._title, True, (10, 10, 10))
        sub_s = (self._font(14).render(self._sub, True, C_TEXT)
                 if self._sub else None)

        band_h = 64 + (24 if sub_s else 0)
        band = pygame.Surface((MAP_RECT.width, band_h), pygame.SRCALPHA)
        band.fill((0, 0, 0, int(150 * alpha / 255)))
        line_col = (*self._color, alpha)
        pygame.draw.line(band, line_col, (0, 1), (MAP_RECT.width, 1), 2)
        pygame.draw.line(band, line_col,
                         (0, band_h - 2), (MAP_RECT.width, band_h - 2), 2)
        band_y = cy - band_h // 2
        surface.blit(band, (MAP_RECT.x, band_y))

        for s, off in ((shadow_s, 2), (title_s, 0)):
            s.set_alpha(alpha)
            surface.blit(s, s.get_rect(centerx=cx - slide + off,
                                       top=band_y + 8 + off))

        if sub_s:
            sub_s.set_alpha(alpha)
            surface.blit(sub_s, sub_s.get_rect(centerx=cx + slide,
                                               top=band_y + band_h - 30))
