"""Bots spelen volledige spellen tegen de engine. Controleert invarianten en rapporteert statistiek.

uv run python scripts/simulate.py --games 300
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from weerwolven.engine import NIGHT_PHASES, Game, GameError  # noqa: E402
from weerwolven import narration  # noqa: E402


def play(seed: int, verbose: bool = False) -> dict:
    rng = random.Random(seed)
    g = Game(seed=seed)
    g.start_game()
    for n in g.names:
        g.ack_reveal(n)
    steps = 0
    narr_kinds = Counter()
    while g.phase != "end":
        steps += 1
        if steps > 400:
            raise AssertionError(f"seed {seed}: spel loopt vast in fase {g.phase}")
        ph = g.phase
        alive = g.alive()
        if ph in NIGHT_PHASES:
            # iedereen in willekeurige volgorde
            order = alive[:]
            rng.shuffle(order)
            wolf_pick = rng.choice([n for n in alive if g.role_of(n) != "weerwolf"])
            for n in order:
                if g.phase != ph:
                    break
                if n in g.night["done"]:
                    continue
                role = g.role_of(n)
                others = [x for x in alive if x != n]
                try:
                    if ph == "night_cupido" and role == "cupido":
                        a, b = rng.sample(alive, 2)
                        g.submit_cupido(n, a, b)
                    elif ph == "night_wolves" and role == "weerwolf":
                        # 20% kans op onenigheid eerst
                        t = wolf_pick if rng.random() > 0.2 else rng.choice([x for x in alive if g.role_of(x) != "weerwolf"])
                        g.submit_wolf(n, t)
                    elif ph == "night_wolves" and role == "ziener":
                        g.submit_seer(n, rng.choice(others))
                    elif ph == "night_witch" and role == "heks":
                        heal = g.witch_potions["heal"] and g.night["wolf_target"] and rng.random() < 0.4
                        poison = rng.choice(others) if g.witch_potions["poison"] and rng.random() < 0.3 else None
                        g.submit_witch(n, heal=bool(heal), poison=poison)
                    else:
                        g.submit_gossip(n, rng.choice(others))
                except GameError as e:
                    raise AssertionError(f"seed {seed} fase {ph} speler {n} ({role}): {e}") from e
            if g.phase == ph and g.night.get("wolf_disagree"):
                continue
            if g.phase == ph and rng.random() < 0.05:
                g.force_night_step()
        elif ph == "hunter":
            h = g.hunter_pending
            g.submit_hunter(h, rng.choice([x for x in alive if x != h]))
        elif ph == "day":
            g.start_vote()
        elif ph == "vote":
            cands = g.vote_candidates()
            for n in alive:
                if g.phase != "vote":
                    break
                opts = [c for c in cands if c != n]
                # bots stemmen vaak hetzelfde zodat er uitslagen komen
                t = (opts[0] if rng.random() < 0.6 else rng.choice(opts)) if opts else None
                if rng.random() < 0.05:
                    t = None
                g.submit_vote(n, t)
        elif ph == "dusk":
            g.begin_night()
        else:
            raise AssertionError(f"seed {seed}: onverwachte fase {ph}")
        # invarianten
        for n in g.names:
            p = g.players[n]
            if not p["alive"]:
                assert p["death_cause"], f"seed {seed}: dode zonder oorzaak"
        pub = g.public_view()
        for p in pub["players"]:
            if p["alive"] and g.phase != "end":
                assert p["role"] is None, f"seed {seed}: rol gelekt van levende speler"
        # fallback narration must render for current state
        for kind in ("morning", "lynch", "hunter_shot", "end", "intro", "dusk", "tie"):
            txt = narration.fallback_text(kind, g, rng)
            assert isinstance(txt, str)
    # eindcontrole winnaar
    wolves = g.alive_with_role("weerwolf")
    others = [n for n in g.alive() if g.role_of(n) != "weerwolf"]
    if g.winner == "dorp":
        assert not wolves
    elif g.winner == "wolven":
        assert len(wolves) >= len(others)
    elif g.winner == "geliefden":
        assert len(g.alive()) == 2
    assert narration.fallback_text("end", g, rng)
    return {"winner": g.winner, "days": g.day, "steps": steps, "alive": len(g.alive())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    winners = Counter()
    days = Counter()
    for i in range(args.games):
        res = play(args.seed + i)
        winners[res["winner"]] += 1
        days[res["days"]] += 1
    print(f"{args.games} spellen gespeeld zonder fouten.")
    print("Winnaars:", dict(winners))
    print("Aantal nachten:", dict(sorted(days.items())))


if __name__ == "__main__":
    main()
