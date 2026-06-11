"""End-of-turn battle animation — map zoom, territory flicker, gunfire sound."""
from __future__ import annotations
import sys
import pygame
from typing import List, Optional, Callable

from config import (SCREEN_W, SCREEN_H, MAP_W, MAP_H, MAP_RECT,
                    FACTION_COLORS, C_BG, FPS)
from game.faction import Faction
from game.events import BattleEvent, BattleResult
from game.combat import full_battle


def _make_gunshot() -> Optional[pygame.mixer.Sound]:
    """Synthesize a short gunfire burst — sharp attack, fast decay."""
    try:
        import numpy as np
        rate = 44100
        n = int(rate * 0.13)
        t = np.linspace(0, 1.0, n)
        noise = np.random.uniform(-1.0, 1.0, n)
        envelope = np.exp(-t * 11) * (1.0 - np.exp(-t * 350))
        samples = (noise * envelope * 28000).astype(np.int16)
        stereo = np.column_stack([samples, samples])
        return pygame.sndarray.make_sound(stereo)
    except Exception:
        return None


class BattleAnimator:
    _ZOOM_TARGET    = 3.2
    _ZOOM_FRAMES    = 28
    _FLICKER_FRAMES = 56
    _SETTLE_FRAMES  = 45
    _UNZOOM_FRAMES  = 22
    _SHOT_EVERY     = 8   # fire sound every N flicker frames

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._shot: Optional[pygame.mixer.Sound] = None
        self._sound_ready = False
        # Reusable surfaces — allocated lazily after display is up
        self._offscreen: Optional[pygame.Surface] = None
        self._map_img: Optional[pygame.Surface] = None
        # Font for the battle banner
        self._banner_font: Optional[pygame.font.Font] = None

    # ── public ────────────────────────────────────────────────────────────────

    def play_sequence(self, world, events: List[BattleEvent],
                      hud_fn: Callable[[pygame.Surface], None]
                      ) -> List[BattleResult]:
        """
        Animate and resolve every BattleEvent in order.
        hud_fn(surface) draws the HUD overlay on top of the map each frame.
        Mutates territory state (armies, owner) as each battle settles.
        """
        self._ensure_surfaces()
        self._init_sound()
        clock = pygame.time.Clock()
        results: List[BattleResult] = []

        for ev in events:
            # Source fell to another faction earlier this round — the staged
            # army was overrun with it, so the attack dissolves.
            if ev.src.owner != ev.attacker_faction:
                results.append(BattleResult(ev, False,
                                            ev.src.armies, ev.tgt.armies))
                continue

            # Skip if the target already belongs to the attacker (captured by an
            # earlier event in this same sequence).
            if ev.tgt.owner == ev.attacker_faction:
                ev.src.armies += ev.attacking_count  # return committed armies
                results.append(BattleResult(ev, False,
                                            ev.src.armies, ev.tgt.armies))
                continue

            r = self._play_one(world, ev, hud_fn, clock)
            results.append(r)
            # Apply outcome to world state (defender losses persist either way)
            ev.src.armies = r.src_survivors
            ev.tgt.armies = r.tgt_armies
            if r.captured:
                ev.tgt.owner = ev.attacker_faction

        return results

    # ── internal ──────────────────────────────────────────────────────────────

    def _play_one(self, world, ev: BattleEvent,
                  hud_fn, clock) -> BattleResult:
        # Resolve the battle in advance — animation is pure theatre
        src_rem, tgt_final, captured = full_battle(
            ev.src.armies + ev.attacking_count,  # total armies at source
            ev.tgt.armies,
            ev.attacking_count,
        )

        att_col = FACTION_COLORS[int(ev.attacker_faction)]
        def_col = ((90, 90, 80) if ev.tgt.owner == Faction.NEUTRAL
                   else FACTION_COLORS[int(ev.tgt.owner)])

        # Convert territory center to map-local coordinates
        cx, cy = ev.tgt.center
        cx_l = cx - MAP_RECT.x
        cy_l = cy - MAP_RECT.y

        def frame(zoom: float, override_col=None):
            ov = {ev.tgt.id: override_col} if override_col else {}
            self._draw_frame(world, cx_l, cy_l, zoom, ov, hud_fn, ev)
            clock.tick(FPS)

        # Zoom in
        for i in range(self._ZOOM_FRAMES):
            t = i / max(self._ZOOM_FRAMES - 1, 1)
            frame(1.0 + (self._ZOOM_TARGET - 1.0) * _ease_in(t))

        # Flicker + gunfire
        for i in range(self._FLICKER_FRAMES):
            col = att_col if (i // 4) % 2 == 0 else def_col
            frame(self._ZOOM_TARGET, col)
            if i % self._SHOT_EVERY == 0 and self._shot:
                self._shot.play()

        # Settle on winner
        winner_col = att_col if captured else def_col
        for _ in range(self._SETTLE_FRAMES):
            frame(self._ZOOM_TARGET, winner_col)

        # Zoom out
        for i in range(self._UNZOOM_FRAMES):
            t = i / max(self._UNZOOM_FRAMES - 1, 1)
            frame(self._ZOOM_TARGET - (self._ZOOM_TARGET - 1.0) * _ease_out(t))

        return BattleResult(ev, captured, src_rem, tgt_final)

    def _draw_frame(self, world, cx_l: int, cy_l: int, zoom: float,
                    override_colors: dict,
                    hud_fn: Callable[[pygame.Surface], None],
                    ev: BattleEvent):
        from ui.map_view import draw_map

        # Render the full scene to the offscreen buffer
        self._offscreen.fill(C_BG)
        draw_map(self._offscreen, world, None, None, None,
                 override_colors=override_colors)

        # Extract just the map region into map_img
        self._map_img.blit(self._offscreen, (0, 0), MAP_RECT)

        # Compute zoom viewport in map-local pixel space
        view_w = max(2, int(MAP_W / zoom))
        view_h = max(2, int(MAP_H / zoom))
        x0 = max(0, min(cx_l - view_w // 2, MAP_W - view_w))
        y0 = max(0, min(cy_l - view_h // 2, MAP_H - view_h))
        # Guard against subsurface overflow
        view_w = min(view_w, MAP_W - x0)
        view_h = min(view_h, MAP_H - y0)

        sub = self._map_img.subsurface(pygame.Rect(x0, y0, view_w, view_h))
        scaled = pygame.transform.scale(sub, (MAP_W, MAP_H))

        # Composite onto real screen
        self.screen.fill(C_BG)
        self.screen.blit(scaled, MAP_RECT.topleft)
        hud_fn(self.screen)
        self._draw_banner(ev)
        self._pump()
        pygame.display.flip()

    def _draw_banner(self, ev: BattleEvent):
        """Overlay the attacker→territory label at the top edge of the map."""
        from config import FACTION_NAMES
        if self._banner_font is None:
            self._banner_font = pygame.font.SysFont("arial", 16, bold=True)
        att_name = FACTION_NAMES[int(ev.attacker_faction)].upper()
        msg = f"{att_name}  →  {ev.tgt.name.upper()}"
        surf = self._banner_font.render(msg, True, (255, 220, 50))
        x = MAP_RECT.centerx - surf.get_width() // 2
        y = MAP_RECT.top + 6
        # Dark backing strip
        pad = 6
        bg = pygame.Surface((surf.get_width() + pad * 2, surf.get_height() + 4),
                             pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        self.screen.blit(bg, (x - pad, y - 2))
        self.screen.blit(surf, (x, y))

    def _ensure_surfaces(self):
        if self._offscreen is None:
            self._offscreen = pygame.Surface((SCREEN_W, SCREEN_H))
            self._map_img = pygame.Surface((MAP_W, MAP_H))

    def _init_sound(self):
        if self._sound_ready:
            return
        self._sound_ready = True
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(44100, -16, 2, 512)
            except Exception:
                return
        self._shot = _make_gunshot()

    @staticmethod
    def _pump():
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()


# ── easing helpers ────────────────────────────────────────────────────────────

def _ease_in(t: float) -> float:
    return t * t


def _ease_out(t: float) -> float:
    return 1.0 - (1.0 - t) ** 2
