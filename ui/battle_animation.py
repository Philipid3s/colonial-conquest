"""End-of-turn battle animation — zoom, live combat rounds, verdict stamp.

Each staged battle zooms into the contested territory, shows an attack
arrow and a panel with both armies, then plays the actual dice rounds:
the territory flickers, muzzle flashes pop inside it, and the army
counters tick down with each round. A CAPTURED/REPULSED stamp (with a
little screen shake on capture) settles the result before zooming out.

SPACE/ENTER/click skips the current battle, ESC fast-forwards the rest.
"""
from __future__ import annotations
import random
import sys
import pygame
from typing import List, Optional, Callable

from config import (SCREEN_W, SCREEN_H, MAP_W, MAP_H, MAP_RECT,
                    FACTION_COLORS, FACTION_NAMES, C_BG, C_WHITE, FPS,
                    C_TERRITORY_NEUTRAL)
from game.faction import Faction
from game.events import BattleEvent, BattleResult
from game.combat import battle_rounds
from game.world import _point_in_poly


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


def _make_boom() -> Optional[pygame.mixer.Sound]:
    """Synthesize a low capture 'boom' — decaying sine + noise burst."""
    try:
        import numpy as np
        rate = 44100
        n = int(rate * 0.45)
        t = np.linspace(0, 0.45, n)
        wave = np.sin(2 * np.pi * 72 * t * (1.0 - 0.25 * t)) * np.exp(-t * 7)
        noise = np.random.uniform(-1.0, 1.0, n) * np.exp(-t * 20) * 0.4
        s = ((wave + noise) * 24000).clip(-32767, 32767).astype(np.int16)
        return pygame.sndarray.make_sound(np.column_stack([s, s]))
    except Exception:
        return None


class BattleAnimator:
    _ZOOM_TARGET   = 3.2
    _ZOOM_FRAMES   = 24
    _SETTLE_FRAMES = 46
    _UNZOOM_FRAMES = 18
    _ROUND_BUDGET  = 52   # total frames for the combat rounds of one battle

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._shot: Optional[pygame.mixer.Sound] = None
        self._boom: Optional[pygame.mixer.Sound] = None
        self._sound_ready = False
        # Reusable surfaces — allocated lazily after display is up
        self._offscreen: Optional[pygame.Surface] = None
        self._map_img: Optional[pygame.Surface] = None
        self._fonts: dict = {}
        # per-sequence skip state
        self._skip_battle = False
        self._skip_all = False
        # per-battle scene state (set by _play_one, read by _draw_frame)
        self._scene: dict = {}

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
        self._skip_all = False
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
        # Resolve the battle in advance — the animation replays the rounds
        rounds, src_rem, tgt_final, captured = battle_rounds(
            ev.src.armies + ev.attacking_count,  # total armies at source
            ev.tgt.armies,
            ev.attacking_count,
        )

        att_col = FACTION_COLORS[int(ev.attacker_faction)]
        def_col = (C_TERRITORY_NEUTRAL if ev.tgt.owner == Faction.NEUTRAL
                   else FACTION_COLORS[int(ev.tgt.owner)])

        # Map-local coordinates (offset into the map image)
        tx, ty = ev.tgt.center
        cx_l, cy_l = tx - MAP_RECT.x, ty - MAP_RECT.y
        sx, sy = ev.src.center
        sx_l, sy_l = sx - MAP_RECT.x, sy - MAP_RECT.y

        self._scene = {
            "ev": ev,
            "att_col": att_col, "def_col": def_col,
            "att_count": ev.attacking_count, "def_count": ev.tgt.armies,
            "arrow": ((sx_l, sy_l), (cx_l, cy_l)),
            "arrow_alpha": 0.0,
            "flashes": [],          # [{pos, age, max_age, size}]
            "stamp": None,          # (text, color, progress 0..1)
            "shake": 0,
        }
        self._skip_battle = False

        def frame(zoom: float, override_col=None):
            ov = {ev.tgt.id: override_col} if override_col else {}
            self._draw_frame(world, cx_l, cy_l, zoom, ov, hud_fn, ev)
            self._advance_effects()
            clock.tick(FPS)

        if not self._skip_all:
            # Zoom in, arrow fading in
            for i in range(self._ZOOM_FRAMES):
                if self._skip_battle or self._skip_all:
                    break
                t = i / max(self._ZOOM_FRAMES - 1, 1)
                self._scene["arrow_alpha"] = t
                frame(1.0 + (self._ZOOM_TARGET - 1.0) * _ease_in(t))

        if not (self._skip_battle or self._skip_all):
            # Combat rounds — compress so long fights stay snappy
            per_round = max(5, min(16, self._ROUND_BUDGET // max(len(rounds), 1)))
            for res, att_left, def_left in rounds:
                if self._skip_battle or self._skip_all:
                    break
                if self._shot:
                    self._shot.play()
                self._spawn_flashes(ev, count=random.randint(2, 4))
                for i in range(per_round):
                    if self._skip_battle or self._skip_all:
                        break
                    # counters tick down mid-round
                    if i == per_round // 2:
                        self._scene["att_count"] = att_left
                        self._scene["def_count"] = def_left
                    col = att_col if (i // 3) % 2 == 0 else def_col
                    frame(self._ZOOM_TARGET, col)

        # Final counters (in case rounds were skipped mid-way)
        last_att = rounds[-1][1] if rounds else ev.attacking_count
        last_def = rounds[-1][2] if rounds else ev.tgt.armies
        self._scene["att_count"] = last_att
        self._scene["def_count"] = last_def
        self._scene["arrow_alpha"] = 1.0

        # Verdict: stamp + (on capture) boom and screen shake
        winner_col = att_col if captured else def_col
        text = "CAPTURED!" if captured else "REPULSED!"
        if not self._skip_all:
            if captured and self._boom:
                self._boom.play()
            self._skip_battle = False  # settle is always shown, but skippable
            settle = self._SETTLE_FRAMES
            for i in range(settle):
                if self._skip_battle or self._skip_all:
                    break
                self._scene["stamp"] = (text, winner_col,
                                        min(1.0, i / 9.0))
                self._scene["shake"] = max(0, 5 - i) if captured else 0
                frame(self._ZOOM_TARGET, winner_col)

            # Zoom out
            self._scene["shake"] = 0
            self._scene["arrow_alpha"] = 0.0
            for i in range(self._UNZOOM_FRAMES):
                if self._skip_all:
                    break
                t = i / max(self._UNZOOM_FRAMES - 1, 1)
                self._scene["stamp"] = (text, winner_col, 1.0 - t)
                frame(self._ZOOM_TARGET
                      - (self._ZOOM_TARGET - 1.0) * _ease_out(t))

        self._scene["stamp"] = None
        return BattleResult(ev, captured, src_rem, tgt_final)

    # ── effects ───────────────────────────────────────────────────────────────

    def _spawn_flashes(self, ev: BattleEvent, count: int):
        """Muzzle flashes at random points inside the target territory."""
        if not ev.tgt.polys:
            return
        # largest ring + its bbox, in map-local space
        idx = max(range(len(ev.tgt.polys)),
                  key=lambda i: (ev.tgt.bboxes[i][2] - ev.tgt.bboxes[i][0])
                              * (ev.tgt.bboxes[i][3] - ev.tgt.bboxes[i][1]))
        x0, y0, x1, y1 = ev.tgt.bboxes[idx]
        ring = ev.tgt.polys[idx]
        for _ in range(count):
            for _try in range(12):
                px = random.uniform(x0, x1)
                py = random.uniform(y0, y1)
                if _point_in_poly((px, py), ring):
                    self._scene["flashes"].append({
                        "pos": (px - MAP_RECT.x, py - MAP_RECT.y),
                        "age": 0,
                        "max_age": random.randint(4, 7),
                        "size": random.randint(2, 5),
                    })
                    break

    def _advance_effects(self):
        flashes = self._scene.get("flashes", [])
        for f in flashes:
            f["age"] += 1
        self._scene["flashes"] = [f for f in flashes if f["age"] <= f["max_age"]]

    def _draw_effects_on_map(self):
        """Arrow + flashes, drawn in map-local space so they zoom with it."""
        sc = self._scene
        alpha = sc.get("arrow_alpha", 0.0)
        if alpha > 0.05:
            (ax, ay), (bx, by) = sc["arrow"]
            col = sc["att_col"]
            dx, dy = bx - ax, by - ay
            dist = max((dx * dx + dy * dy) ** 0.5, 1.0)
            ux, uy = dx / dist, dy / dist
            # only show the final approach (huge territories like Russia have
            # their center half a world away), and stop short of the badge
            if dist > 80:
                ax, ay = bx - ux * 80, by - uy * 80
            ex, ey = bx - ux * 8, by - uy * 8
            # white shaft with dark outline reads on any terrain color
            pygame.draw.line(self._map_img, (0, 0, 0), (ax + 1, ay + 1),
                             (ex + 1, ey + 1), 5)
            pygame.draw.line(self._map_img, (245, 245, 235),
                             (ax, ay), (ex, ey), 3)
            # arrowhead
            px, py = -uy, ux
            head = [(ex + ux * 3, ey + uy * 3),
                    (ex - ux * 8 + px * 6, ey - uy * 8 + py * 6),
                    (ex - ux * 8 - px * 6, ey - uy * 8 - py * 6)]
            pygame.draw.polygon(self._map_img, (0, 0, 0),
                                [(hx + 1, hy + 1) for hx, hy in head])
            pygame.draw.polygon(self._map_img, col, head)

        for f in sc.get("flashes", []):
            fade = 1.0 - f["age"] / f["max_age"]
            r = max(1, int(f["size"] * (0.6 + fade)))
            x, y = int(f["pos"][0]), int(f["pos"][1])
            pygame.draw.circle(self._map_img, (255, 170, 60), (x, y), r + 1)
            pygame.draw.circle(self._map_img, (255, 255, 220), (x, y), max(1, r - 1))

    # ── frame composition ─────────────────────────────────────────────────────

    def _draw_frame(self, world, cx_l: int, cy_l: int, zoom: float,
                    override_colors: dict,
                    hud_fn: Callable[[pygame.Surface], None],
                    ev: BattleEvent):
        from ui.map_view import draw_map

        # Render the full scene to the offscreen buffer
        self._offscreen.fill(C_BG)
        draw_map(self._offscreen, world, None, None, None,
                 override_colors=override_colors)

        # Extract just the map region into map_img, add zooming effects
        self._map_img.blit(self._offscreen, (0, 0), MAP_RECT)
        self._draw_effects_on_map()

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

        # Composite onto real screen (with capture shake)
        shake = self._scene.get("shake", 0)
        ox = random.randint(-shake, shake) if shake else 0
        oy = random.randint(-shake, shake) if shake else 0

        self.screen.fill(C_BG)
        self.screen.blit(scaled, (MAP_RECT.x + ox, MAP_RECT.y + oy))
        hud_fn(self.screen)
        self._draw_panel(ev)
        self._draw_stamp()
        self._draw_skip_hint()
        self._pump()
        pygame.display.flip()

    def _font(self, size: int, bold: bool = True) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.SysFont("arial", size, bold=bold)
        return self._fonts[key]

    def _draw_panel(self, ev: BattleEvent):
        """Live battle panel: [attacker n] vs [n defender] over the map top."""
        sc = self._scene
        f_name = self._font(14)
        f_num = self._font(18)
        f_vs = self._font(12)

        att_name = FACTION_NAMES[int(ev.attacker_faction)].upper()
        def_name = ("NEUTRAL" if ev.tgt.owner == Faction.NEUTRAL
                    else FACTION_NAMES[int(ev.tgt.owner)].upper())

        att_s = f_name.render(att_name, True, C_WHITE)
        def_s = f_name.render(def_name, True, C_WHITE)
        att_n = f_num.render(str(sc["att_count"]), True, C_WHITE)
        def_n = f_num.render(str(sc["def_count"]), True, C_WHITE)
        vs_s = f_vs.render("VS", True, (220, 210, 160))
        tgt_s = self._font(12).render(ev.tgt.name.upper(), True, (255, 220, 50))

        pad, gap, h = 10, 14, 34
        att_w = att_s.get_width() + att_n.get_width() + pad * 3
        def_w = def_s.get_width() + def_n.get_width() + pad * 3
        total = att_w + gap + vs_s.get_width() + gap + def_w
        x = MAP_RECT.centerx - total // 2
        y = MAP_RECT.top + 8

        strip = pygame.Surface((total + 16, h + tgt_s.get_height() + 10),
                               pygame.SRCALPHA)
        strip.fill((0, 0, 0, 150))
        self.screen.blit(strip, (x - 8, y - 4))

        def box(bx, w, color, name_s, num_s, num_first):
            rect = pygame.Rect(bx, y, w, h)
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            pygame.draw.rect(self.screen, (0, 0, 0), rect, 1, border_radius=5)
            items = (num_s, name_s) if num_first else (name_s, num_s)
            ix = bx + pad
            for s in items:
                self.screen.blit(s, (ix, y + (h - s.get_height()) // 2))
                ix += s.get_width() + pad

        box(x, att_w, sc["att_col"], att_s, att_n, num_first=False)
        self.screen.blit(vs_s, (x + att_w + gap,
                                y + (h - vs_s.get_height()) // 2))
        box(x + att_w + gap + vs_s.get_width() + gap, def_w,
            sc["def_col"], def_s, def_n, num_first=True)

        self.screen.blit(tgt_s, (MAP_RECT.centerx - tgt_s.get_width() // 2,
                                 y + h + 2))

    def _draw_stamp(self):
        stamp = self._scene.get("stamp")
        if not stamp:
            return
        text, color, progress = stamp
        if progress <= 0.0:
            return
        # scale in with a slight overshoot, fade with progress
        scale = 1.0 + 0.9 * (1.0 - _ease_out(min(progress, 1.0)))
        base = self._font(42).render(text, True, color)
        outline = self._font(42).render(text, True, (10, 10, 10))
        w = max(1, int(base.get_width() * scale))
        h = max(1, int(base.get_height() * scale))
        base = pygame.transform.smoothscale(base, (w, h))
        outline = pygame.transform.smoothscale(outline, (w, h))
        alpha = int(255 * min(1.0, progress * 1.6))
        base.set_alpha(alpha)
        outline.set_alpha(alpha)
        cx, cy = MAP_RECT.centerx, MAP_RECT.centery + 60
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            self.screen.blit(outline, outline.get_rect(center=(cx + dx, cy + dy)))
        self.screen.blit(base, base.get_rect(center=(cx, cy)))

    def _draw_skip_hint(self):
        hint = self._font(11, bold=False).render(
            "SPACE: skip battle   ·   ESC: skip all", True, (170, 170, 160))
        bg = pygame.Surface((hint.get_width() + 12, hint.get_height() + 6),
                            pygame.SRCALPHA)
        bg.fill((0, 0, 0, 130))
        x = MAP_RECT.centerx - hint.get_width() // 2
        y = MAP_RECT.bottom - hint.get_height() - 10
        self.screen.blit(bg, (x - 6, y - 3))
        self.screen.blit(hint, (x, y))

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
        self._boom = _make_boom()

    def _pump(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self._skip_all = True
                elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self._skip_battle = True
            elif e.type == pygame.MOUSEBUTTONDOWN:
                self._skip_battle = True


# ── easing helpers ────────────────────────────────────────────────────────────

def _ease_in(t: float) -> float:
    return t * t


def _ease_out(t: float) -> float:
    return 1.0 - (1.0 - t) ** 2
