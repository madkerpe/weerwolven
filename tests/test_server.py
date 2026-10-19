import json

import pytest
from fastapi.testclient import TestClient

from weerwolven.engine import Game, NIGHT_PHASES
from weerwolven.server import Client, Hub, create_app


class FakeWS:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_text(self, s: str):
        self.sent.append(json.loads(s))


class Conn:
    def __init__(self, hub: Hub):
        self.hub = hub
        self.ws = FakeWS()
        self.c = Client(self.ws)

    async def send(self, msg: dict):
        await self.hub.handle(self.c, msg)

    def last(self, kind="state"):
        for m in reversed(self.ws.sent):
            if m["type"] == kind:
                return m["view"] if kind == "state" else m
        return None

    def has(self, kind):
        return any(m["type"] == kind for m in self.ws.sent)


@pytest.fixture
def hub():
    return Hub(game=Game(seed=99), save=False)


async def test_full_game_over_hub(hub):
    g = hub.game
    screen = Conn(hub)
    await screen.send({"type": "hello", "kind": "screen"})
    assert screen.last()["phase"] == "lobby" and screen.last()["join_url"].startswith("http://")
    host = Conn(hub)
    await host.send({"type": "hello", "kind": "host", "key": g.host_key})
    assert host.last()["host"]["actions"][0]["id"] == "start"
    bad = Conn(hub)
    await bad.send({"type": "hello", "kind": "host", "key": "0000"})
    assert bad.last("error")["fatal"]

    players: dict[str, Conn] = {}
    for n in g.names:
        p = Conn(hub)
        await p.send({"type": "hello", "kind": "player"})
        await p.send({"type": "claim", "name": n})
        assert p.last("claimed")["name"] == n
        assert p.last()["me"]["name"] == n
        players[n] = p
    dup = Conn(hub)
    await dup.send({"type": "hello", "kind": "player"})
    await dup.send({"type": "claim", "name": "Bram"})
    assert "ingenomen" in dup.last("error")["text"]
    assert all(p["connected"] for p in screen.last()["players"])

    await host.send({"type": "host", "action": "start"})
    assert g.phase == "reveal"
    assert any(x["kind"] == "intro" and x["status"] == "ready" for x in g.narrations)
    # elke speler ziet eigen rol, niemand anders
    for n, p in players.items():
        me = p.last()["me"]
        assert me["role"] == g.role_of(n)
        assert me["personage"]["titel"]
        assert all(q["role"] is None for q in p.last()["players"])
    for p in players.values():
        await p.send({"type": "act", "action": "ack"})
    assert g.phase == "night_cupido"
    assert any(x["kind"] == "night_cupido" for x in g.narrations)

    async def act(n, **kw):
        await players[n].send({"type": "act", **kw})

    for _ in range(3):
        ph = g.phase
        if ph not in NIGHT_PHASES:
            break
        alive = g.alive()
        for n in alive:
            if g.phase != ph:
                break
            role = g.role_of(n)
            others = [x for x in alive if x != n]
            if ph == "night_cupido" and role == "cupido":
                await act(n, action="cupido", a=others[0], b=others[1])
            elif ph == "night_wolves" and role == "weerwolf":
                await act(n, action="wolf", target=next(x for x in alive if g.role_of(x) != "weerwolf"))
            elif ph == "night_wolves" and role == "ziener":
                await act(n, action="seer", target=others[0])
                assert "is " in players[n].last()["me"]["prompt"]["text"]
            elif ph == "night_witch" and role == "heks":
                assert players[n].last()["me"]["prompt"]["kind"] == "witch"
                await act(n, action="witch", heal=False, poison=None)
            else:
                assert players[n].last()["me"]["prompt"].get("decoy")
                await act(n, action="gossip", target=others[0])
    if g.phase == "hunter":
        await act(g.hunter_pending, action="hunter", target=[x for x in g.alive() if x != g.hunter_pending][0])
    assert g.phase in ("day", "end")
    morning = next(x for x in g.narrations if x["kind"] == "morning")
    if not any(x["kind"] == "hunter" for x in g.narrations):
        assert morning["instruction"]
    else:
        assert morning["instruction"] == ""  # de jagerstekst draagt dan de instructie
    # intro: verhaal en instructie gescheiden, nachtstappen elk een eigen batch
    intro = next(x for x in g.narrations if x["kind"] == "intro")
    assert "Gelezen" in intro["instruction"] and "Gelezen" not in intro["text"]
    nights = [x for x in g.narrations if x["kind"].startswith("night_")]
    assert len({x["batch"] for x in nights}) == len(nights)
    # screen shows narration + progress fields
    sv = screen.last()
    assert sv["narrations"][-1]["status"] == "ready"
    if g.phase == "end":
        return
    # host vrije tekst
    await host.send({"type": "host_text", "text": "start de stemming"})
    assert g.phase == "vote"
    target = g.alive()[0]
    await host.send({"type": "host_text", "text": f"we hebben gestemd op {target.lower()} en die is dood"})
    assert g.pending_confirm and g.pending_confirm["command"]["target"] == target
    assert host.last()["host"]["pending_confirm"]["text"].startswith(target)
    await host.send({"type": "host", "action": "reject"})
    assert g.pending_confirm is None and g.players[target]["alive"]
    await host.send({"type": "host_text", "text": f"{target} is dood"})
    await host.send({"type": "host", "action": "confirm"})
    assert not g.players[target]["alive"]
    assert g.phase in ("dusk", "hunter", "end")
    await host.send({"type": "host_text", "text": "herhaal"})
    assert g.repeat["seq"] == 1
    # onbegrepen tekst zonder LLM
    await host.send({"type": "host_text", "text": "blablabla"})
    assert "Niet begrepen" in host.last()["host"]["answer"]
    # chat
    alive_name = g.alive()[0]
    await players[alive_name].send({"type": "chat", "channel": "public", "text": "hallo dorp"})
    assert screen.last()["chat"][-1]["text"] == "hallo dorp"
    with_wolf = next((n for n in g.alive() if g.role_of(n) == "weerwolf"), None)
    if with_wolf:
        await players[with_wolf].send({"type": "chat", "channel": "wolves", "text": "grr"})
        assert players[with_wolf].last()["private_chat"]["wolves"][-1]["text"] == "grr"
        assert "grr" not in json.dumps(screen.last())
    for p in screen.last()["players"]:
        if p["alive"]:
            assert p["role"] is None


async def test_reconnect_and_reset_seat(hub):
    g = hub.game
    p = Conn(hub)
    await p.send({"type": "hello", "kind": "player"})
    await p.send({"type": "claim", "name": "Ninke"})
    tok = p.last("claimed")["token"]
    p2 = Conn(hub)
    await p2.send({"type": "hello", "kind": "player", "name": "Ninke", "token": tok})
    assert p2.last()["me"]["name"] == "Ninke"
    wrong = Conn(hub)
    await wrong.send({"type": "hello", "kind": "player", "name": "Ninke", "token": "fout"})
    assert "me" not in wrong.last()
    host = Conn(hub)
    await host.send({"type": "hello", "kind": "host", "key": g.host_key})
    await host.send({"type": "host", "action": "reset_seat", "target": "Ninke"})
    assert p2.has("kicked")
    await wrong.send({"type": "claim", "name": "Ninke", "token": "fout"})
    assert wrong.last("claimed")["name"] == "Ninke"


async def test_persisted_state_reloads(tmp_path, monkeypatch):
    from weerwolven import server
    monkeypatch.setattr(server, "STATE_PATH", tmp_path / "state.json")
    h = Hub(game=Game(seed=5), save=True)
    host = Conn(h)
    await host.send({"type": "hello", "kind": "host", "key": h.game.host_key})
    await host.send({"type": "host", "action": "start"})
    assert (tmp_path / "state.json").exists()
    h2 = Hub(save=True)
    assert h2.game.phase == "reveal" and h2.game.host_key == h.game.host_key


def test_http_routes(hub):
    app = create_app(hub)
    with TestClient(app) as client:
        r = client.get("/api/state")
        assert r.status_code == 200 and r.json()["phase"] == "lobby"
        assert client.get("/").status_code == 200
        assert client.get("/screen").status_code == 200
        assert client.get("/host").status_code == 200
        assert client.get("/qr.svg").headers["content-type"].startswith("image/svg")


async def test_new_game_narrates_again(hub):
    g = hub.game
    host = Conn(hub)
    await host.send({"type": "hello", "kind": "host", "key": g.host_key})
    await host.send({"type": "host", "action": "start"})
    assert any(x["kind"] == "intro" for x in g.narrations)
    await host.send({"type": "host", "action": "new_game"})
    assert g.narrations == []
    await host.send({"type": "host", "action": "start"})
    assert any(x["kind"] == "intro" for x in g.narrations), "na nieuw spel moet de intro opnieuw verteld worden"


async def test_restart_resumes_narration(tmp_path, monkeypatch):
    from weerwolven import server
    monkeypatch.setattr(server, "STATE_PATH", tmp_path / "state.json")
    h = Hub(game=Game(seed=5), save=True)
    host = Conn(h)
    await host.send({"type": "hello", "kind": "host", "key": h.game.host_key})
    await host.send({"type": "host", "action": "start"})
    h.game.narrations = []  # alsof er nooit verteld werd
    h.save()
    h2 = Hub(save=True)
    host2 = Conn(h2)
    await host2.send({"type": "hello", "kind": "host", "key": h2.game.host_key})
    await host2.send({"type": "host", "action": "force_ack"})
    kinds = [x["kind"] for x in h2.game.narrations]
    assert "intro" in kinds and "night_cupido" in kinds
