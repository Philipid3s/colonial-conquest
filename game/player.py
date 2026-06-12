from __future__ import annotations
from dataclasses import dataclass
from game.faction import Faction, faction_name


@dataclass
class Player:
    faction: Faction
    is_human: bool = True
    gold: int = 0
    alive: bool = True

    # armies purchased this turn, pending placement
    pending_armies: int = 0

    @property
    def name(self) -> str:
        return faction_name(self.faction)

    def collect_income(self, territories) -> int:
        income = sum(t.income for t in territories if t.owner == self.faction)
        self.gold += income
        return income

    def can_buy_army(self) -> bool:
        from config import ARMY_COST
        return self.gold >= ARMY_COST

    def buy_army(self) -> bool:
        from config import ARMY_COST
        if self.gold >= ARMY_COST:
            self.gold -= ARMY_COST
            self.pending_armies += 1
            return True
        return False

    def affordable_armies(self) -> int:
        from config import ARMY_COST
        return self.gold // ARMY_COST

    def buy_armies(self, count: int) -> int:
        """Buy up to `count` armies into the pending pool. Returns how many."""
        bought = 0
        while bought < count and self.buy_army():
            bought += 1
        return bought

    def reinforce(self, territory, count: int = 1) -> int:
        """Place up to `count` armies on an owned territory, drawing from the
        pending pool first and then buying with gold. Returns how many."""
        if territory.owner != self.faction:
            return 0
        placed = 0
        for _ in range(count):
            if self.pending_armies == 0 and not self.buy_army():
                break
            self.pending_armies -= 1
            territory.armies += 1
            placed += 1
        return placed

    def place_army(self, territory) -> bool:
        if self.pending_armies > 0 and territory.owner == self.faction:
            territory.armies += 1
            self.pending_armies -= 1
            return True
        return False

    def reset_turn(self):
        self.pending_armies = 0
