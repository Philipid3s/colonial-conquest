"""Simple AI — prioritises attacking weak neighbours and reinforcing borders."""
from __future__ import annotations
import random
from typing import List, Optional, Tuple
from game.player import Player
from game.territory import Territory
from game.world import World
from config import MIN_ATTACK_ARMIES


class AIController:
    def __init__(self, player: Player, world: World):
        self.player = player
        self.world = world

    def do_purchase(self):
        """Spend all gold on armies, then place them on border territories."""
        while self.player.can_buy_army():
            self.player.buy_army()
        self._place_armies()

    def _place_armies(self):
        border = self._border_territories()
        owned = self.world.owned_by(self.player.faction)
        targets = border if border else owned
        if not targets:
            return
        while self.player.pending_armies > 0:
            t = random.choice(targets)
            self.player.place_army(t)

    def plan_attacks(self) -> list:
        """
        Choose attack targets (up to 5), commit armies by setting src.armies = 1,
        and return a list of BattleEvents for the animator to resolve.
        Does NOT execute combat — call BattleAnimator.play_sequence to do that.
        """
        from game.events import BattleEvent
        events = []
        for _ in range(5):
            attack = self._pick_attack()
            if not attack:
                break
            src, tgt = attack
            attacking = src.armies - 1
            src.armies = 1  # armies committed; survivors returned after animation
            events.append(BattleEvent(src, tgt, self.player.faction, attacking))
        return events

    def do_moves(self):
        """Reinforce weak border territories from safe interior ones."""
        border_ids = {t.id for t in self._border_territories()}
        interior = [t for t in self.world.owned_by(self.player.faction)
                    if t.id not in border_ids and t.armies > 2]
        for src in interior:
            # find a neighbouring owned territory that is on the border
            for nid in src.neighbors:
                nb = self.world.territories[nid]
                if nb.owner == self.player.faction and nb.id in border_ids:
                    transfer = src.armies - 1
                    src.armies -= transfer
                    nb.armies += transfer
                    break

    # ── helpers ──────────────────────────────────────────────────────────────

    def _border_territories(self) -> List[Territory]:
        """Owned territories that touch at least one enemy/neutral territory."""
        result = []
        for t in self.world.owned_by(self.player.faction):
            for nid in t.neighbors + t.sea_links:
                nb = self.world.territories[nid]
                if nb.owner != self.player.faction:
                    result.append(t)
                    break
        return result

    def _pick_attack(self) -> Optional[Tuple[Territory, Territory]]:
        """Pick the best (src, tgt) attack pair: most armies vs. fewest defenders."""
        best = None
        best_score = -1
        for src in self.world.owned_by(self.player.faction):
            if src.armies < MIN_ATTACK_ARMIES:
                continue
            for nid in src.neighbors + src.sea_links:
                tgt = self.world.territories[nid]
                if tgt.owner == self.player.faction:
                    continue
                score = src.armies - tgt.armies
                if score > best_score:
                    best_score = score
                    best = (src, tgt)
        return best
