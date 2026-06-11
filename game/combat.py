"""Combat resolution — dice-based like the original Colonial Conquest."""
from __future__ import annotations
import random
from dataclasses import dataclass
from typing import List, Tuple

from config import ATTACKER_DICE, DEFENDER_DICE


@dataclass
class CombatResult:
    attacker_losses: int
    defender_losses: int
    territory_captured: bool
    attacker_dice_rolls: List[int]
    defender_dice_rolls: List[int]


def resolve_combat(attacker_armies: int, defender_armies: int,
                   attacking_count: int) -> CombatResult:
    """
    Resolve one combat round.
    attacking_count: armies committed to the attack (must leave ≥1 behind).
    Returns losses for this round; caller loops until capture or retreat.
    """
    att_dice = min(ATTACKER_DICE, attacking_count)
    def_dice = min(DEFENDER_DICE, defender_armies)

    att_rolls = sorted([random.randint(1, 6) for _ in range(att_dice)], reverse=True)
    def_rolls = sorted([random.randint(1, 6) for _ in range(def_dice)], reverse=True)

    att_loss = 0
    def_loss = 0
    for a, d in zip(att_rolls, def_rolls):
        if a > d:
            def_loss += 1
        else:
            att_loss += 1

    captured = (defender_armies - def_loss) <= 0

    return CombatResult(
        attacker_losses=att_loss,
        defender_losses=def_loss,
        territory_captured=captured,
        attacker_dice_rolls=att_rolls,
        defender_dice_rolls=def_rolls,
    )


def battle_rounds(attacker_armies: int, defender_armies: int,
                  attacking_count: int
                  ) -> Tuple[List[Tuple[CombatResult, int, int]], int, int, bool]:
    """
    Fight until the territory is captured or the attacker cannot continue,
    keeping the per-round progression (for animation).
    Returns (rounds, remaining_attacker_armies_in_source,
             final_target_garrison, captured) where rounds is a list of
    (CombatResult, attackers_left, defenders_left) snapshots.
    """
    att = attacking_count
    dfd = defender_armies
    source_remainder = attacker_armies - attacking_count  # must stay behind
    rounds: List[Tuple[CombatResult, int, int]] = []

    while att >= 1 and dfd > 0:
        result = resolve_combat(att + source_remainder, dfd, att)
        att -= result.attacker_losses
        dfd -= result.defender_losses
        rounds.append((result, max(att, 0), max(dfd, 0)))
        if att < 1:
            break

    # Capture needs at least one attacker left standing to occupy.
    if dfd <= 0 and att >= 1:
        return rounds, source_remainder, att, True
    return rounds, source_remainder + max(att, 0), max(dfd, 0), False


def full_battle(attacker_armies: int, defender_armies: int,
                attacking_count: int) -> Tuple[int, int, bool]:
    """
    Fight until the territory is captured or the attacker cannot continue.
    Returns (remaining_attacker_armies_in_source, final_target_garrison, captured).
    final_target_garrison is the occupying force on capture, or the surviving
    defenders on a failed attack (defender losses persist either way).
    """
    _rounds, src_rem, tgt_final, captured = battle_rounds(
        attacker_armies, defender_armies, attacking_count)
    return src_rem, tgt_final, captured
