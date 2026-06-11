"""Colonial Conquest — pygame remake entry point."""
import sys
import pygame

from config import (SCREEN_W, SCREEN_H, FPS, MAP_RECT,
                    PHASE_PURCHASE, PHASE_MOVE, PHASE_ATTACK,
                    MIN_ATTACK_ARMIES)
from game.faction import Faction
from game.player import Player
from game.world import World
from game.turn import TurnManager
from game.events import BattleEvent
from game.ai import AIController
from ui.renderer import Renderer
from ui.battle_animation import BattleAnimator
from ui.menu import StartMenu
from ui.gameover import GameOverScreen
from ui.amount_dialog import AmountDialog
from ui.camera import Camera


def make_players(human_faction: Faction) -> list:
    factions = [Faction.USA, Faction.USSR, Faction.CHINA,
                Faction.BRITAIN, Faction.GERMANY, Faction.JAPAN]
    return [Player(faction=f, is_human=(f == human_faction), gold=10)
            for f in factions]


class GameState:
    """Mutable UI/interaction state, separate from game logic."""
    def __init__(self):
        self.selected = None
        self.hovered  = None
        self.interaction_mode = None   # "move" | "attack" | None
        self.valid_targets: set = set()
        self.message = ""
        self.attack_queue: list = []   # human's staged attacks this phase
        self.drag_from = None          # screen pos of an active map drag

    def clear_selection(self):
        self.selected = None
        self.valid_targets = set()
        self.interaction_mode = None

    def select(self, territory, mode, world, player):
        self.selected = territory
        self.interaction_mode = mode
        self._compute_targets(world, player)

    def _compute_targets(self, world, player):
        t = self.selected
        mode = self.interaction_mode
        if t is None or mode is None:
            self.valid_targets = set()
            return
        if mode == "move":
            self.valid_targets = {
                nid for nid in t.neighbors + t.sea_links
                if world.territories[nid].owner == player.faction}
        elif mode == "attack":
            self.valid_targets = {
                nid for nid in t.neighbors + t.sea_links
                if world.territories[nid].owner != player.faction}


def check_game_over(world, players):
    """Return the winning player if the game has ended, else None."""
    alive = [p for p in players if p.alive]
    human = next(p for p in players if p.is_human)
    for p in alive:
        if world.check_victory(p.faction):
            return p
    if len(alive) == 1:
        return alive[0]
    if not human.alive:
        # Human is out — game over; report the current leader as winner
        return max(alive, key=lambda p: len(world.owned_by(p.faction)))
    return None


# ── end-of-round battle resolution ───────────────────────────────────────────

def _run_combined_battles(battle_turn, players, turn_mgr, world,
                          state, animator, renderer):
    """Animate and resolve all staged battles from this round."""
    def hud_fn(surf):
        renderer.hud.draw(surf, battle_turn, PHASE_ATTACK,
                          turn_mgr.current_player, players,
                          None, "BATTLE RESOLUTION")

    animator.play_sequence(world, turn_mgr.round_battles, hud_fn)
    turn_mgr.round_battles.clear()
    turn_mgr.check_eliminations(world)
    state.message = f"Turn {battle_turn} battles resolved."


def _end_attack_phase(player, turn_mgr, world, state,
                      animator, renderer, players) -> bool:
    """
    Flush the human's staged attacks, advance past the attack phase,
    and trigger the combined animation if this was the last player.
    Returns True if the animation ran (caller should not advance phase again).
    """
    turn_mgr.round_battles.extend(state.attack_queue)
    state.attack_queue.clear()

    is_last = turn_mgr.is_last_player()
    battle_turn = turn_mgr.turn_number

    # Advance ATTACK → END → next player (skips the empty END phase)
    turn_mgr.advance_phase(world)  # ATTACK → END
    turn_mgr.advance_phase(world)  # END → next player's PURCHASE (income auto)
    turn_mgr.check_eliminations(world)

    if is_last and turn_mgr.round_battles:
        _run_combined_battles(battle_turn, players, turn_mgr,
                              world, state, animator, renderer)

    return is_last


# ── AI turn ───────────────────────────────────────────────────────────────────

def run_ai_turn(player, turn_mgr, world, state,
                animator, renderer, players) -> bool:
    """
    Execute one AI player's full turn.
    Stages attacks into turn_mgr.round_battles (does NOT resolve them yet).
    Advances through PHASE_END so the main loop sees the next player directly.
    Returns True if this was the last player — the combined animation ran.
    """
    ai = AIController(player, world)
    ai.do_purchase()
    turn_mgr.advance_phase(world)   # PURCHASE → MOVE
    ai.do_moves()
    turn_mgr.advance_phase(world)   # MOVE → ATTACK

    events = ai.plan_attacks()
    turn_mgr.round_battles.extend(events)

    is_last = turn_mgr.is_last_player()
    battle_turn = turn_mgr.turn_number

    turn_mgr.advance_phase(world)   # ATTACK → END
    turn_mgr.advance_phase(world)   # END → next player's PURCHASE (income auto)
    turn_mgr.check_eliminations(world)
    state.message = f"{player.name} finished their turn."

    if is_last and turn_mgr.round_battles:
        _run_combined_battles(battle_turn, players, turn_mgr,
                              world, state, animator, renderer)

    return is_last


# ── button / click handlers ───────────────────────────────────────────────────

def handle_button(action, player, phase, turn_mgr, world, state,
                  animator, renderer, players):
    if action == "buy_army":
        if player.can_buy_army():
            player.buy_army()
            state.message = (f"Army purchased. "
                             f"Pending: {player.pending_armies}  Gold: ${player.gold}")

    elif action == "end_turn":
        state.clear_selection()
        if phase == PHASE_ATTACK:
            _end_attack_phase(player, turn_mgr, world, state,
                              animator, renderer, players)
        else:
            turn_mgr.advance_phase(world)
            turn_mgr.check_eliminations(world)
        state.message = f"Phase: {turn_mgr.current_phase.upper()}"


def handle_map_click(clicked, player, phase, world, turn_mgr, state, dialog):
    # Place pending armies immediately on click
    if phase == PHASE_PURCHASE and player.pending_armies > 0:
        if clicked.owner == player.faction:
            player.place_army(clicked)
            state.message = (f"Placed in {clicked.name}. "
                             f"Pending: {player.pending_armies}")
        return

    if phase == PHASE_MOVE:
        if state.selected is None:
            if clicked.owner == player.faction and clicked.armies > 1:
                state.select(clicked, "move", world, player)
                state.message = f"Moving from {clicked.name} — click destination."
        else:
            if clicked.id in state.valid_targets:
                amount = dialog.run(
                    f"Move how many armies to {clicked.name}?",
                    state.selected.armies - 1)
                if amount:
                    state.selected.armies -= amount
                    clicked.armies += amount
                    state.message = f"Moved {amount} to {clicked.name}."
            state.clear_selection()
        return

    if phase == PHASE_ATTACK:
        if state.selected is None:
            if (clicked.owner == player.faction
                    and clicked.armies >= MIN_ATTACK_ARMIES):
                state.select(clicked, "attack", world, player)
                state.message = f"Attacking from {clicked.name} — click target."
        else:
            if clicked.id in state.valid_targets:
                amount = dialog.run(
                    f"Attack {clicked.name} with how many armies?",
                    state.selected.armies - 1)
                if amount:
                    state.selected.armies -= amount  # committed until resolution
                    state.attack_queue.append(
                        BattleEvent(state.selected, clicked,
                                    player.faction, amount))
                    state.message = (f"Attack on {clicked.name} queued "
                                     f"({amount} armies).")
            state.clear_selection()
        return

    # Fallback: select / deselect
    if state.selected is not clicked:
        state.selected = clicked
        state.valid_targets = set()
        state.interaction_mode = None
    else:
        state.clear_selection()


# ── main ──────────────────────────────────────────────────────────────────────

def run_game(screen, clock):
    """One full game: menu → play → game-over. Returns to caller for restart."""
    world = World()

    # Show title screen; player picks their faction
    chosen_faction = StartMenu(screen, world).run()

    players = make_players(chosen_faction)
    world.place_starting_armies(players)

    turn_mgr = TurnManager(players)
    renderer = Renderer(screen)
    animator = BattleAnimator(screen)
    dialog   = AmountDialog(screen)
    state    = GameState()
    camera   = Camera()

    # Skip automatic income phase on game start
    if turn_mgr.current_phase == "income":
        turn_mgr.advance_phase(world)

    while True:
        winner = check_game_over(world, players)
        if winner is not None:
            human = next(p for p in players if p.is_human)
            GameOverScreen(screen, world, winner, human,
                           turn_mgr.turn_number).run()
            return

        player = turn_mgr.current_player
        phase  = turn_mgr.current_phase

        # AI takes its full turn automatically then loops back
        if not player.is_human and player.alive:
            pygame.time.delay(300)
            run_ai_turn(player, turn_mgr, world, state,
                        animator, renderer, players)
            state.clear_selection()
            continue

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.MOUSEMOTION:
                renderer.handle_motion(event.pos)
                if state.drag_from:
                    camera.pan(state.drag_from[0] - event.pos[0],
                               state.drag_from[1] - event.pos[1])
                    state.drag_from = event.pos
                state.hovered = (
                    world.territory_at(camera.screen_to_world(event.pos))
                    if MAP_RECT.collidepoint(event.pos) else None)

            elif event.type == pygame.MOUSEWHEEL:
                mpos = pygame.mouse.get_pos()
                if MAP_RECT.collidepoint(mpos):
                    camera.zoom_at(mpos, 1.15 if event.y > 0 else 1 / 1.15)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                action = renderer.handle_click(event.pos)
                if action:
                    handle_button(action, player, phase, turn_mgr, world, state,
                                  animator, renderer, players)
                elif MAP_RECT.collidepoint(event.pos):
                    clicked = world.territory_at(
                        camera.screen_to_world(event.pos))
                    if clicked:
                        handle_map_click(clicked, player, phase,
                                         world, turn_mgr, state, dialog)

            elif (event.type == pygame.MOUSEBUTTONDOWN
                    and event.button in (2, 3)
                    and MAP_RECT.collidepoint(event.pos)):
                state.drag_from = event.pos

            elif event.type == pygame.MOUSEBUTTONUP and event.button in (2, 3):
                state.drag_from = None

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    state.clear_selection()
                elif event.key == pygame.K_r:
                    camera.reset()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    state.clear_selection()
                    if phase == PHASE_ATTACK:
                        _end_attack_phase(player, turn_mgr, world, state,
                                          animator, renderer, players)
                    else:
                        turn_mgr.advance_phase(world)
                        turn_mgr.check_eliminations(world)
                    state.message = f"Phase: {turn_mgr.current_phase.upper()}"

        # Smooth keyboard panning (held arrow keys)
        keys = pygame.key.get_pressed()
        pan_px = 14
        dx = pan_px * (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT])
        dy = pan_px * (keys[pygame.K_DOWN] - keys[pygame.K_UP])
        if dx or dy:
            camera.pan(dx, dy)

        renderer.draw(world, turn_mgr.turn_number, phase,
                      player, players,
                      state.selected, state.hovered,
                      state.valid_targets, state.message,
                      camera=camera)
        clock.tick(FPS)


def main():
    pygame.init()
    pygame.display.set_caption("Colonial Conquest")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock  = pygame.time.Clock()

    while True:
        run_game(screen, clock)


if __name__ == "__main__":
    main()
