"""Map camera — pan/zoom viewport over the projected world map.

World space is the fixed pixel space territories are projected into at
startup (MAP_RECT-anchored). The camera maps a sub-rectangle of it onto
MAP_RECT; at zoom 1.0 it is the identity transform.
"""
from __future__ import annotations
from typing import Tuple

from config import MAP_RECT


class Camera:
    MIN_ZOOM = 1.0
    MAX_ZOOM = 6.0

    def __init__(self):
        self.zoom = 1.0
        self.off_x = 0.0   # viewport top-left in world px, relative to MAP_RECT
        self.off_y = 0.0
        self.version = 0   # bumped on every change — used as a render-cache key

    @property
    def is_identity(self) -> bool:
        return self.zoom == 1.0

    def world_to_screen(self, p: Tuple[float, float]) -> Tuple[int, int]:
        return (int(MAP_RECT.x + ((p[0] - MAP_RECT.x) - self.off_x) * self.zoom),
                int(MAP_RECT.y + ((p[1] - MAP_RECT.y) - self.off_y) * self.zoom))

    def screen_to_world(self, p: Tuple[float, float]) -> Tuple[float, float]:
        return ((p[0] - MAP_RECT.x) / self.zoom + self.off_x + MAP_RECT.x,
                (p[1] - MAP_RECT.y) / self.zoom + self.off_y + MAP_RECT.y)

    def viewport_world(self) -> Tuple[float, float, float, float]:
        """Visible world-space rect as (x0, y0, x1, y1), MAP_RECT-absolute."""
        x0 = MAP_RECT.x + self.off_x
        y0 = MAP_RECT.y + self.off_y
        return (x0, y0,
                x0 + MAP_RECT.width / self.zoom,
                y0 + MAP_RECT.height / self.zoom)

    def pan(self, dx_screen: float, dy_screen: float):
        """Shift the view by a screen-space delta (drag direction)."""
        self.off_x += dx_screen / self.zoom
        self.off_y += dy_screen / self.zoom
        self._clamp()
        self.version += 1

    def zoom_at(self, screen_pos: Tuple[int, int], factor: float):
        """Zoom keeping the world point under screen_pos stationary."""
        anchor = self.screen_to_world(screen_pos)
        self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self.zoom * factor))
        # re-solve offset so anchor stays under the cursor
        self.off_x = (anchor[0] - MAP_RECT.x) - (screen_pos[0] - MAP_RECT.x) / self.zoom
        self.off_y = (anchor[1] - MAP_RECT.y) - (screen_pos[1] - MAP_RECT.y) / self.zoom
        self._clamp()
        self.version += 1

    def reset(self):
        self.zoom = 1.0
        self.off_x = self.off_y = 0.0
        self.version += 1

    def _clamp(self):
        max_x = MAP_RECT.width - MAP_RECT.width / self.zoom
        max_y = MAP_RECT.height - MAP_RECT.height / self.zoom
        self.off_x = max(0.0, min(self.off_x, max_x))
        self.off_y = max(0.0, min(self.off_y, max_y))
