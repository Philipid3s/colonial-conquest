from enum import IntEnum
from config import FACTION_COLORS, FACTION_NAMES


class Faction(IntEnum):
    USA     = 0
    USSR    = 1
    CHINA   = 2
    BRITAIN = 3
    GERMANY = 4
    JAPAN   = 5
    NEUTRAL = 6


def faction_color(f: Faction) -> tuple:
    return FACTION_COLORS[int(f)]


def faction_name(f: Faction) -> str:
    return FACTION_NAMES[int(f)]
