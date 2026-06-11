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

    def place_army(self, territory) -> bool:
        if self.pending_armies > 0 and territory.owner == self.faction:
            territory.armies += 1
            self.pending_armies -= 1
            return True
        return False

    def reset_turn(self):
        self.pending_armies = 0
