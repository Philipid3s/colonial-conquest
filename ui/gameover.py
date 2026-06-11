"""Game-over screen — victory or defeat, with the final map behind it."""
from __future__ import annotations
import sys
import pygame

from config import (SCREEN_W, SCREEN_H, C_BG, C_GOLD,
                    FACTION_COLORS, FACTION_NAMES)
from game.player import Player
from game.world import World
from ui.map_view import draw_map


def _font(size: int, bold: bool = False) -> pygame.font.Font:
    return pygame.font.SysFont("arial", size, bold=bold)


class GameOverScreen:
    """Shows the result over the final map. Returns 'menu' or quits."""

    def __init__(self, screen: pygame.Surface, world: World,
                 winner: Player, human: Player, turn: int):
        self.screen = screen
        self.world = world
        self.winner = winner
        self.human = human
        self.turn = turn

    def run(self) -> str:
        base = pygame.Surface((SCREEN_W, SCREEN_H))
        base.fill(C_BG)
        draw_map(base, self.world, None, None, None)
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((6, 10, 20, 190))

        won = self.winner is self.human
        title = "VICTORY" if won else "DEFEAT"
        title_col = C_GOLD if won else (200, 70, 70)
        w_col = FACTION_COLORS[int(self.winner.faction)]
        w_name = FACTION_NAMES[int(self.winner.faction)]
        owned = len(self.world.owned_by(self.winner.faction))
        total = self.world.total_territories()

        clock = pygame.time.Clock()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
                    return "menu"
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    return "menu"

            self.screen.blit(base, (0, 0))
            self.screen.blit(overlay, (0, 0))

            t_surf = _font(64, bold=True).render(title, True, title_col)
            self.screen.blit(t_surf, t_surf.get_rect(centerx=SCREEN_W // 2, y=220))

            sub = f"{w_name} dominates the world  ·  {owned}/{total} territories  ·  Turn {self.turn}"
            s_surf = _font(16).render(sub, True, w_col)
            self.screen.blit(s_surf, s_surf.get_rect(centerx=SCREEN_W // 2, y=320))

            hint = _font(12).render(
                "Press any key to return to the menu  ·  ESC to quit",
                True, (160, 160, 150))
            self.screen.blit(hint, hint.get_rect(centerx=SCREEN_W // 2, y=380))

            pygame.display.flip()
            clock.tick(30)
