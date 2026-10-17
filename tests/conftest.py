import os
os.environ["WW_NO_LLM"] = "1"
os.environ["WW_STATE"] = "/dev/null"

import pytest
from weerwolven.engine import Game, NIGHT_PHASES


def roles(g: Game) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for n in g.names:
        out.setdefault(g.players[n]["role"], []).append(n)
    return out


def do_night(g: Game, wolf_target=None, seer_target=None, heal=False, poison=None, lovers=None):
    """Laat iedereen zijn nachtstappen doen. Wolven kiezen wolf_target (of eerste niet-wolf)."""
    for _ in range(3):
        if g.phase not in NIGHT_PHASES:
            return
        ph = g.phase
        alive = g.alive()
        others = lambda n: [x for x in alive if x != n]
        for n in alive:
            if g.phase != ph:
                break
            role = g.role_of(n)
            if ph == "night_cupido" and role == "cupido":
                a, b = lovers or [x for x in alive][:2]
                g.submit_cupido(n, a, b)
            elif ph == "night_wolves" and role == "weerwolf":
                t = wolf_target or next(x for x in alive if g.role_of(x) != "weerwolf")
                g.submit_wolf(n, t)
            elif ph == "night_wolves" and role == "ziener":
                g.submit_seer(n, seer_target or others(n)[0])
            elif ph == "night_witch" and role == "heks":
                g.submit_witch(n, heal=heal, poison=poison)
            else:
                g.submit_gossip(n, others(n)[0])


def do_vote(g: Game, target: str, voters=None):
    g.start_vote() if g.phase == "day" else None
    for n in g.alive():
        if g.phase != "vote":
            break
        g.submit_vote(n, target if n != target else None)


def started(seed=1) -> Game:
    g = Game(seed=seed)
    g.start_game()
    for n in g.names:
        g.ack_reveal(n)
    return g


@pytest.fixture
def game():
    return started()
