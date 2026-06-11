"""Shared event dataclasses for combat — kept in game/ to avoid circular imports."""
from __future__ import annotations
from dataclasses import dataclass
from game.territory import Territory
from game.faction import Faction


@dataclass
class BattleEvent:
    src: Territory
    tgt: Territory
    attacker_faction: Faction
    attacking_count: int   # armies committed (already deducted from src.armies)


@dataclass
class BattleResult:
    event: BattleEvent
    captured: bool
    src_survivors: int     # armies that remain in / return to src
    tgt_armies: int        # final garrison: occupiers on capture, surviving defenders on failure
