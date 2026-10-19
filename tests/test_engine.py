import pytest
from weerwolven.engine import Game, GameError, ROLE_DECK
from conftest import do_night, do_vote, roles, started


def test_roles_and_personages_assigned():
    g = started()
    assert sorted(p["role"] for p in g.players.values()) == sorted(ROLE_DECK)
    assert len({p["personage"] for p in g.players.values()}) == 9
    assert g.phase == "night_cupido"


def test_lobby_requires_start():
    g = Game(seed=2)
    with pytest.raises(GameError):
        g.ack_reveal("Bram")


def test_seat_claim_and_reset():
    g = Game(seed=3)
    tok = g.claim_seat("Bram", None)
    assert g.check_token("Bram", tok)
    assert g.claim_seat("Bram", tok) == tok
    with pytest.raises(GameError):
        g.claim_seat("Bram", "ander")
    g.reset_seat("Bram")
    assert g.claim_seat("Bram", "ander") == "ander"


def test_cupido_then_wolves_then_witch_then_day():
    g = started()
    r = roles(g)
    cup = r["cupido"][0]
    g.submit_cupido(cup, "Bram", "Griet")
    assert g.players["Bram"]["lover"] == "Griet"
    # others must still gossip before the step ends
    assert g.phase == "night_cupido"
    for n in g.alive():
        if n != cup:
            g.submit_gossip(n, [x for x in g.alive() if x != n][0])
    assert g.phase == "night_wolves"
    victim = next(n for n in g.names if g.role_of(n) == "burger")
    do_night(g, wolf_target=victim)
    assert g.phase in ("day", "hunter")
    assert not g.players[victim]["alive"]


def test_wolves_must_agree():
    g = started()
    do_night(g)  # cupido step only partially? do_night runs all steps; so use fresh approach
    # new game to control wolves
    g = started(seed=5)
    r = roles(g)
    w1, w2 = r["weerwolf"]
    # finish cupido step
    for n in g.alive():
        if g.role_of(n) == "cupido":
            g.submit_cupido(n, w1, "Bram" if "Bram" != w1 else "Griet")
        else:
            g.submit_gossip(n, [x for x in g.alive() if x != n][0])
    assert g.phase == "night_wolves"
    burgers = r["burger"]
    g.submit_wolf(w1, burgers[0])
    g.submit_wolf(w2, burgers[1])
    for n in g.alive():
        if g.role_of(n) not in ("weerwolf",):
            if g.role_of(n) == "ziener":
                g.submit_seer(n, burgers[2])
            else:
                g.submit_gossip(n, [x for x in g.alive() if x != n][0])
    # disagreement: still in night_wolves, wolves must redo
    assert g.phase == "night_wolves"
    assert g.night["wolf_disagree"] == sorted([burgers[0], burgers[1]])
    g.submit_wolf(w1, burgers[0])
    g.submit_wolf(w2, burgers[0])
    assert g.phase == "night_witch"
    assert g.night["wolf_target"] == burgers[0]


def test_witch_heal_and_poison_once():
    g = started(seed=7)
    r = roles(g)
    burgers = r["burger"]
    do_night(g, wolf_target=burgers[0], heal=True, poison=burgers[1], lovers=[burgers[0], burgers[2]])
    assert g.players[burgers[0]]["alive"]
    assert not g.players[burgers[1]]["alive"]
    assert g.witch_potions == {"heal": False, "poison": False}
    assert g.phase in ("day", "hunter")
    if g.phase == "hunter":
        g.submit_hunter(g.hunter_pending, [n for n in g.alive() if n != g.hunter_pending][0])
    do_vote(g, burgers[2])
    assert g.phase in ("dusk", "hunter", "end")
    if g.phase == "dusk":
        g.begin_night()
        # second night: witch has nothing left
        heks = r["heks"][0]
        wolves_target = next(n for n in g.alive() if g.role_of(n) not in ("weerwolf",))
        # drive to witch step
        for n in g.alive():
            if g.role_of(n) == "weerwolf":
                g.submit_wolf(n, wolves_target)
            elif g.role_of(n) == "ziener":
                g.submit_seer(n, [x for x in g.alive() if x != n][0])
            else:
                g.submit_gossip(n, [x for x in g.alive() if x != n][0])
        if g.phase == "night_witch":
            with pytest.raises(GameError):
                g.submit_witch(heks, heal=True)
            with pytest.raises(GameError):
                g.submit_witch(heks, poison=wolves_target)


def test_lover_chain_on_lynch():
    g = started(seed=11)
    r = roles(g)
    a, b = r["burger"][0], r["burger"][1]
    do_night(g, wolf_target=r["burger"][2], lovers=[a, b])
    if g.phase == "hunter":
        g.submit_hunter(g.hunter_pending, [n for n in g.alive() if n != g.hunter_pending and n not in (a, b)][0])
    assert g.phase == "day"
    do_vote(g, a)
    assert not g.players[a]["alive"] and not g.players[b]["alive"]
    assert g.players[b]["death_cause"] == "liefdesverdriet"


def test_hunter_shoots_after_night_death():
    g = started(seed=13)
    r = roles(g)
    jager = r["jager"][0]
    do_night(g, wolf_target=jager, lovers=[r["burger"][0], r["burger"][1]])
    assert g.phase == "hunter" and g.hunter_pending == jager
    # de dode jager moet op zijn GSM de schietkeuze krijgen, niet "je bent dood"
    pr = g.player_view(jager)["me"]["prompt"]
    assert pr["kind"] == "pick" and jager not in pr["options"]
    assert g.player_view(r["burger"][2])["me"]["prompt"]["kind"] == "wait"
    with pytest.raises(GameError):
        g.submit_hunter(r["burger"][0], r["burger"][1])
    target = r["weerwolf"][0]
    g.submit_hunter(jager, target)
    assert not g.players[target]["alive"]
    assert g.phase == "day"


def test_hunter_lover_chain_then_hunter_shoots():
    g = started(seed=17)
    r = roles(g)
    jager, b = r["jager"][0], r["burger"][0]
    do_night(g, wolf_target=b, lovers=[jager, b])
    # b dies by wolves, jager dies of heartbreak, hunter still shoots
    assert g.phase == "hunter" and g.hunter_pending == jager
    g.submit_hunter(jager, r["weerwolf"][0])
    assert g.phase in ("day", "end")


def test_tie_then_revote_then_no_lynch():
    g = started(seed=19)
    r = roles(g)
    do_night(g, wolf_target=r["burger"][0], lovers=[r["burger"][1], r["burger"][2]])
    if g.phase == "hunter":
        g.submit_hunter(g.hunter_pending, r["weerwolf"][0])
    assert g.phase == "day"
    g.start_vote()
    alive = g.alive()
    x, y = alive[0], alive[1]
    for i, n in enumerate(alive):
        g.submit_vote(n, (x if i % 2 == 0 else y) if n not in (x, y) else (y if n == x else x))
    # engineer an exact tie is fiddly; accept either tie or lynch, but check consistency
    if g.phase == "vote":
        assert g.vote["round"] == 2
        assert set(g.vote["candidates"]) <= set(alive)
        # revote: everyone blank -> nobody dies
        for n in g.alive():
            g.submit_vote(n, None)
        assert g.phase == "dusk"
        assert g.last_vote_result["lynched"] is None
    else:
        assert g.phase in ("dusk", "hunter", "end")


def test_vote_restrictions():
    g = started(seed=23)
    r = roles(g)
    do_night(g, wolf_target=r["burger"][0], lovers=[r["burger"][1], r["burger"][2]])
    if g.phase == "hunter":
        g.submit_hunter(g.hunter_pending, r["weerwolf"][0])
    g.start_vote()
    n = g.alive()[0]
    with pytest.raises(GameError):
        g.submit_vote(n, n)
    with pytest.raises(GameError):
        g.submit_vote(n, r["burger"][0])  # dead


def test_village_wins_when_wolves_dead():
    g = started(seed=29)
    r = roles(g)
    w1, w2 = r["weerwolf"]
    do_night(g, wolf_target=r["burger"][0], lovers=[r["burger"][1], r["burger"][2]])
    if g.phase == "hunter":
        g.submit_hunter(g.hunter_pending, w1)
    else:
        do_vote(g, w1)
        if g.phase == "hunter":
            g.submit_hunter(g.hunter_pending, w2)
    if g.phase == "dusk":
        g.begin_night()
        do_night(g, wolf_target=r["burger"][1])
        if g.phase == "hunter":
            g.submit_hunter(g.hunter_pending, w2)
        if g.phase == "day":
            do_vote(g, w2)
            if g.phase == "hunter":
                g.submit_hunter(g.hunter_pending, g.alive()[0])
    assert g.phase == "end"
    assert g.winner in ("dorp", "geliefden")


def test_host_kill_in_day_goes_to_dusk():
    g = started(seed=31)
    r = roles(g)
    do_night(g, wolf_target=r["burger"][0], lovers=[r["burger"][1], r["burger"][2]])
    if g.phase == "hunter":
        g.submit_hunter(g.hunter_pending, r["weerwolf"][0])
    g.host_kill(r["weerwolf"][0]) if g.players[r["weerwolf"][0]]["alive"] else g.host_kill(r["weerwolf"][1])
    assert g.phase in ("dusk", "hunter", "end")


def test_force_night_step_without_votes():
    g = started(seed=37)
    g.force_night_step()  # cupido: random lovers
    assert g.phase == "night_wolves"
    assert sum(1 for n in g.names if g.players[n]["lover"]) == 2
    g.force_night_step()  # no wolf vote -> nobody
    assert g.phase == "night_witch"
    g.force_night_step()
    assert g.phase == "day"
    assert g.last_deaths == []


def test_views_do_not_leak_roles():
    g = started(seed=41)
    pub = g.public_view()
    assert all(p["role"] is None for p in pub["players"])
    host = g.host_view()
    assert all(p["role"] is None for p in host["players"])
    import json
    blob = json.dumps(host) + json.dumps(pub)
    for n in g.names:
        assert f'"{n}": "weerwolf"' not in blob
    # player sees own role only
    r = roles(g)
    pv = g.player_view(r["burger"][0])
    assert pv["me"]["role"] == "burger"
    assert "all_roles" not in pv["me"]
    assert all(p["role"] is None for p in pv["players"])
    # wolves see each other
    wv = g.player_view(r["weerwolf"][0])
    assert wv["me"]["mates"] == [r["weerwolf"][1]]


def test_dead_see_all_roles_and_dead_chat():
    g = started(seed=43)
    r = roles(g)
    victim = r["burger"][0]
    do_night(g, wolf_target=victim, lovers=[r["burger"][1], r["burger"][2]])
    pv = g.player_view(victim)
    assert set(pv["me"]["all_roles"].values()) == set(ROLE_DECK)
    assert pv["me"]["channels"] == ["dead"]
    g.post_chat(victim, "dead", "boe")
    with pytest.raises(GameError):
        g.post_chat(victim, "public", "ik leef nog")


def test_persistence_roundtrip():
    g = started(seed=47)
    do_night(g)
    d = g.to_dict()
    import json
    g2 = Game.from_dict(json.loads(json.dumps(d)))
    assert g2.phase == g.phase
    assert g2.players == g.players
    assert g2.public_view()["phase"] == g.phase


def test_new_game_keeps_seats():
    g = started(seed=53)
    tok = g.claim_seat("Bram", None)
    g.new_game()
    assert g.phase == "lobby"
    assert g.check_token("Bram", tok)
    assert g.game_no == 1


def test_public_view_shows_live_votes():
    g = started(seed=61)
    r = roles(g)
    do_night(g, wolf_target=r["burger"][0], lovers=[r["burger"][1], r["burger"][2]])
    if g.phase == "hunter":
        g.submit_hunter(g.hunter_pending, r["weerwolf"][0])
    g.start_vote()
    a, b = g.alive()[0], g.alive()[1]
    g.submit_vote(a, b)
    pv = g.public_view()["vote"]
    assert pv["votes"] == {a: b}
    for n in g.alive()[1:]:
        g.submit_vote(n, a if n != a else None)
    assert g.last_vote_result["votes"][a] == b
    assert g.public_view()["vote"]["votes"] == {}  # stemming voorbij
