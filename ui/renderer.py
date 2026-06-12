"""Top-level renderer — composes map and HUD each frame."""
from __future__ import annotations
import pygame
from typing import Optional

from config import C_BG
from game.world import World
from game.territory import Territory
from game.player import Player
from ui.map_view import draw_map
from ui.hud import HUD
from ui.phase_banner import PhaseBanner


class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.hud = HUD()
        self.banner = PhaseBanner()

    def draw(self, world: World, turn: int, phase: str,
             current_player: Player, all_players: list,
             selected: Optional[Territory],
             hovered: Optional[Territory],
             valid_targets: Optional[set],
             message: str = "",
             camera=None):
        self.screen.fill(C_BG)
        draw_map(self.screen, world, selected, hovered, valid_targets,
                 camera=camera)
        self.hud.update_buttons(phase, current_player)
        self.hud.draw(self.screen, turn, phase, current_player, all_players,
                      selected, message)
        self.banner.draw(self.screen)
        pygame.display.flip()

    def handle_motion(self, pos):
        self.hud.handle_motion(pos)

    def handle_click(self, pos) -> Optional[str]:
        return self.hud.handle_click(pos)
