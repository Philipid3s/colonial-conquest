"""Turn manager — sequences phases and players."""
from __future__ import annotations
from typing import List, Optional, Callable
from config import PHASES, PHASE_INCOME, PHASE_PURCHASE
from game.player import Player
from game.faction import Faction


class TurnManager:
    def __init__(self, players: List[Player]):
        self.players = [p for p in players if p.faction != Faction.NEUTRAL]
        self.turn_number = 1
        self._player_idx = 0
        self._phase_idx = 0
        # callback hooks
        self.on_phase_change: Optional[Callable] = None
        self.on_player_change: Optional[Callable] = None
        # Accumulates BattleEvents from ALL players this round;
        # cleared after the combined end-of-round animation.
        self.round_battles: list = []

    @property
    def current_player(self) -> Player:
        return self.players[self._player_idx]

    @property
    def current_phase(self) -> str:
        return PHASES[self._phase_idx]

    def advance_phase(self, world) -> bool:
        """
        Move to the next phase.  Returns True if a new player's turn started.
        """
        # Leftover purchased armies must not evaporate at next income's
        # reset_turn() — bank them on the capital before leaving the phase.
        if self.current_phase == PHASE_PURCHASE:
            self._auto_place_pending(world)

        self._phase_idx += 1
        new_player_turn = False

        if self._phase_idx >= len(PHASES):
            self._phase_idx = 0
            self._player_idx += 1
            new_player_turn = True

            # Advance to the next living player, wrapping the round if needed
            for _ in range(len(self.players) * 2):
                if self._player_idx >= len(self.players):
                    self._player_idx = 0
                    self.turn_number += 1
                if self.players[self._player_idx].alive:
                    break
                self._player_idx += 1

            if self.on_player_change:
                self.on_player_change(self.current_player)

        # Auto-process income phase immediately
        if self.current_phase == PHASE_INCOME:
            self._do_income(world)
            self.advance_phase(world)

        if self.on_phase_change:
            self.on_phase_change(self.current_phase)

        return new_player_turn

    def _do_income(self, world):
        p = self.current_player
        p.reset_turn()
        income = p.collect_income(world.territories.values())
        return income

    def _auto_place_pending(self, world):
        """Place any unplaced purchased armies on the capital (or first owned)."""
        p = self.current_player
        if p.pending_armies <= 0:
            return
        owned = world.owned_by(p.faction)
        if owned:
            target = next((t for t in owned if t.capital), owned[0])
            target.armies += p.pending_armies
        p.pending_armies = 0

    def check_eliminations(self, world):
        """Mark players with no territories as eliminated."""
        for p in self.players:
            if not world.owned_by(p.faction):
                p.alive = False

    def alive_players(self) -> List[Player]:
        return [p for p in self.players if p.alive]

    def is_last_player(self) -> bool:
        """True if no other alive player follows the current one this round."""
        return all(not p.alive for p in self.players[self._player_idx + 1:])
