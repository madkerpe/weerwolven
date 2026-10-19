"""FastAPI-server: websocket-hub, per-kijker views, verteller-orkestratie, persistentie."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import socket
from pathlib import Path

import segno
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import hostparse, llm, narration
from .engine import NIGHT_PHASES, Game, GameError

log = logging.getLogger("weerwolven")
STATIC = Path(__file__).parent / "static"
STATE_PATH = Path(os.environ.get("WW_STATE", "state.json"))

EVENT_NARRATION = {
    "start": "intro",
    "night_step": "night_step",
    "morning": "morning",
    "hunter": "hunter",
    "hunter_shot": "hunter_shot",
    "vote_start": "vote_start",
    "tie": "tie",
    "lynch": "lynch",
    "no_lynch": "no_lynch",
    "end": "end",
    "death_host": "death_host",
}


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:  # noqa: BLE001
        return "127.0.0.1"


class Client:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.kind: str | None = None
        self.name: str | None = None

    async def send(self, msg: dict) -> None:
        try:
            await self.ws.send_text(json.dumps(msg, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            pass


class Hub:
    def __init__(self, game: Game | None = None, port: int = 8000, save: bool = True):
        self.game = game or self._load()
        self.port = port
        self.save_enabled = save
        self.clients: list[Client] = []
        self.rng = random.Random()
        self._processed_game = self.game.game_no
        self._processed_event = self._resume_point(self.game)
        self._tasks: set[asyncio.Task] = set()
        self.host_answer: str | None = None
        self.save()  # host-sleutel meteen vastleggen zodat een herstart dezelfde link houdt

    # ------------------------------------------------------------ persistence
    def _load(self) -> Game:
        if STATE_PATH.exists():
            try:
                g = Game.from_dict(json.loads(STATE_PATH.read_text()))
                log.info("Spelstand geladen uit %s (fase %s)", STATE_PATH, g.phase)
                return g
            except Exception as e:  # noqa: BLE001
                log.warning("Kon %s niet laden (%s), nieuw spel.", STATE_PATH, e)
        return Game()

    def save(self) -> None:
        if not self.save_enabled:
            return
        try:
            tmp = STATE_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.game.to_dict(), ensure_ascii=False))
            tmp.replace(STATE_PATH)
        except Exception as e:  # noqa: BLE001
            log.warning("Opslaan mislukt: %s", e)

    def join_url(self) -> str:
        return f"http://{lan_ip()}:{self.port}/"

    # --------------------------------------------------------------- views
    def view_for(self, c: Client) -> dict | None:
        g = self.game
        if c.kind == "screen":
            v = g.public_view()
            v["join_url"] = self.join_url()
            return v
        if c.kind == "host":
            v = g.host_view()
            v["join_url"] = self.join_url()
            v["host"]["answer"] = self.host_answer
            v["host"]["llm"] = llm.available()
            return v
        if c.kind == "player" and c.name:
            return g.player_view(c.name)
        if c.kind == "player":
            v = g.public_view()
            return v
        return None

    async def push(self, c: Client) -> None:
        v = self.view_for(c)
        if v is not None:
            await c.send({"type": "state", "view": v})

    async def broadcast(self) -> None:
        await asyncio.gather(*(self.push(c) for c in list(self.clients)))

    async def changed(self) -> None:
        """Na elke mutatie: vertellen, opslaan, iedereen bijwerken."""
        self._narrate_new_events()
        self.save()
        await self.broadcast()

    # ------------------------------------------------------------ narration
    @staticmethod
    def _resume_point(g: Game) -> int:
        """Na een herstart: ga verder na het laatst vertelde event, maar vertel hoogstens het allerlaatste event alsnog."""
        last_told = max((n.get("event_id") or 0 for n in g.narrations), default=0)
        return max(last_told, g._event_id - 1)

    def _narrate_new_events(self) -> None:
        """Alle nieuwe events van deze mutatie vormen samen een 'batch': ze blijven samen op het scherm."""
        g = self.game
        if g.game_no != self._processed_game:
            # nieuw spel: eventnummers beginnen opnieuw
            self._processed_game = g.game_no
            self._processed_event = 0
        batch = None
        for ev in g.events:
            if ev["id"] <= self._processed_event:
                continue
            self._processed_event = ev["id"]
            kind = EVENT_NARRATION.get(ev["kind"])
            if not kind:
                continue
            if kind == "night_step":
                kind = ev["step"]
            if batch is None:
                g.narr_batch += 1
                batch = g.narr_batch
            instr = narration.instruction_text(kind, g)
            if kind == "death_host":
                g.add_narration(kind, ev["text"], "ready", ev["id"], instruction=instr, batch=batch)
                continue
            fallback = narration.fallback_text(kind, g, self.rng)
            if narration.uses_llm(kind) and llm.available():
                item = g.add_narration(kind, fallback, "thinking", ev["id"], instruction=instr, batch=batch)
                prompt = narration.build_prompt(kind, g, fallback)
                self._spawn(self._generate(item["id"], prompt, fallback))
            else:
                g.add_narration(kind, fallback, "ready", ev["id"], instruction=instr, batch=batch)

    def _spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _generate(self, narr_id: int, prompt: str, fallback: str) -> None:
        text = await llm.ask(prompt)
        if not text or len(text) < 20 or len(text) > 1500:
            text = fallback
        if self.game.update_narration(narr_id, text):
            self.save()
            await self.broadcast()

    # ------------------------------------------------------------- handlers
    async def handle(self, c: Client, msg: dict) -> None:
        g = self.game
        t = msg.get("type")
        try:
            if t == "hello":
                await self._hello(c, msg)
                return
            if c.kind == "player":
                await self._player_msg(c, msg)
            elif c.kind == "host":
                await self._host_msg(c, msg)
            elif c.kind == "screen":
                pass
        except GameError as e:
            await c.send({"type": "error", "text": str(e)})
            await self.push(c)

    async def _hello(self, c: Client, msg: dict) -> None:
        g = self.game
        kind = msg.get("kind")
        if kind == "host":
            if str(msg.get("key")) != g.host_key:
                await c.send({"type": "error", "text": "Verkeerde host-sleutel.", "fatal": True})
                return
            c.kind = "host"
        elif kind == "screen":
            c.kind = "screen"
        else:
            c.kind = "player"
            name, token = msg.get("name"), msg.get("token")
            if name and g.check_token(name, token):
                c.name = name
                g.set_connected(name, +1)
        if c not in self.clients:
            self.clients.append(c)
        await self.changed() if c.name else await self.push(c)

    async def _player_msg(self, c: Client, msg: dict) -> None:
        g = self.game
        t = msg.get("type")
        if t == "claim":
            name = msg.get("name")
            token = g.claim_seat(name, msg.get("token"), same_device=(c.name == name))
            if c.name and c.name != name:
                g.set_connected(c.name, -1)
            c.name = name
            g.set_connected(name, +1)
            await c.send({"type": "claimed", "name": name, "token": token})
            await self.changed()
            return
        if not c.name:
            raise GameError("Kies eerst je naam.")
        if t == "act":
            a = msg.get("action")
            n = c.name
            if a == "ack":
                g.ack_reveal(n)
            elif a == "gossip":
                g.submit_gossip(n, msg.get("target"))
            elif a == "cupido":
                g.submit_cupido(n, msg.get("a"), msg.get("b"))
            elif a == "wolf":
                g.submit_wolf(n, msg.get("target"))
            elif a == "seer":
                g.submit_seer(n, msg.get("target"))
            elif a == "witch":
                g.submit_witch(n, bool(msg.get("heal")), msg.get("poison") or None)
            elif a == "hunter":
                g.submit_hunter(n, msg.get("target"))
            elif a == "vote":
                g.submit_vote(n, msg.get("target") or None)
            else:
                raise GameError("Onbekende actie.")
            await self.changed()
        elif t == "chat":
            g.post_chat(c.name, msg.get("channel", "public"), msg.get("text", ""))
            await self.changed()

    async def _host_msg(self, c: Client, msg: dict) -> None:
        g = self.game
        t = msg.get("type")
        if t == "host":
            await self._host_action(c, msg.get("action"), msg)
        elif t == "host_text":
            await self._host_text(c, (msg.get("text") or "").strip())

    async def _host_action(self, c: Client, action: str, msg: dict) -> None:
        g = self.game
        if action == "start":
            g.start_game()
        elif action == "force_ack":
            g.force_all_ack()
        elif action == "force_step":
            g.force_night_step()
        elif action == "start_vote":
            g.start_vote()
        elif action == "force_vote":
            g.force_vote()
        elif action == "cancel_vote":
            g.cancel_vote()
        elif action == "night":
            g.begin_night()
        elif action == "new_game":
            g.new_game()
        elif action == "repeat":
            g.repeat_narration()
        elif action == "advance":
            g.advance()
        elif action == "kill":
            g.host_kill(msg.get("target"))
        elif action == "reset_seat":
            g.reset_seat(msg.get("target"))
            for cl in self.clients:
                if cl.kind == "player" and cl.name == msg.get("target"):
                    cl.name = None
                    await cl.send({"type": "kicked"})
        elif action == "setting":
            key, val = msg.get("key"), msg.get("value")
            if key in g.settings:
                g.settings[key] = bool(val)
                g._touch()
        elif action == "confirm":
            pc = g.pending_confirm
            g.pending_confirm = None
            if pc:
                await self._execute(c, pc["command"], confirmed=True)
                return
        elif action == "reject":
            g.pending_confirm = None
            g._touch()
        elif action == "clear_answer":
            self.host_answer = None
        else:
            raise GameError(f"Onbekende hostactie: {action}")
        await self.changed()

    async def _host_text(self, c: Client, text: str) -> None:
        g = self.game
        if not text:
            return
        cmd = hostparse.parse(text, g.names, g.phase)
        if cmd["confidence"] >= 0.75 and cmd["cmd"] != "question":
            await self._execute(c, cmd)
            return
        if not llm.available():
            if cmd["cmd"] in ("kill", "reset_seat"):
                await self._execute(c, cmd)
                return
            self.host_answer = f"Niet begrepen: \"{text}\". Gebruik de knoppen of zeg bv. 'Bram is dood', 'volgende', 'herhaal'."
            await self.changed()
            return
        self.host_answer = "De verteller denkt na..."
        await self.changed()
        summary = narration._public_context(g)
        res = await llm.ask(hostparse.llm_prompt(text, g.names, g.phase, summary), schema=hostparse.LLM_SCHEMA, timeout=25)
        if not isinstance(res, dict):
            self.host_answer = f"De verteller begreep \"{text}\" niet. Probeer korter, of gebruik de knoppen."
            await self.changed()
            return
        res["confidence"] = 0.9
        if res.get("cmd") == "question":
            self.host_answer = res.get("answer") or "Daar heb ik geen antwoord op."
            await self.changed()
            return
        if res.get("cmd") == "unknown":
            self.host_answer = res.get("answer") or f"Niet begrepen: \"{text}\"."
            await self.changed()
            return
        if res.get("target") and res["target"] not in g.names:
            found = hostparse.find_names(res["target"], g.names)
            res["target"] = found[0] if found else None
        self.host_answer = None
        await self._execute(c, res)

    async def _execute(self, c: Client, cmd: dict, confirmed: bool = False) -> None:
        g = self.game
        name = cmd.get("cmd")
        if name in ("kill", "new_game", "reset_seat") and not confirmed:
            tgt = cmd.get("target")
            if name == "kill":
                if not tgt:
                    raise GameError("Wie is er dood? Noem een naam.")
                q = f"{tgt} is dood. Klopt dat?"
            elif name == "new_game":
                q = "Een nieuw spel starten en dit spel weggooien?"
            else:
                q = f"De zetel van {tgt} vrijgeven zodat {tgt} op een ander toestel kan inloggen?"
            g.pending_confirm = {"command": cmd, "text": q}
            g._touch()
            await self.changed()
            return
        if name == "advance":
            g.advance()
        elif name == "repeat":
            g.repeat_narration()
        elif name == "start_vote":
            g.start_vote()
        elif name == "cancel_vote":
            g.cancel_vote()
        elif name == "kill":
            g.host_kill(cmd["target"])
        elif name == "new_game":
            g.new_game()
        elif name == "reset_seat":
            await self._host_action(c, "reset_seat", {"target": cmd["target"]})
            return
        else:
            raise GameError("Niet begrepen.")
        self.host_answer = None
        await self.changed()

    # ------------------------------------------------------------ websocket
    async def ws_loop(self, ws: WebSocket) -> None:
        await ws.accept()
        c = Client(ws)
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except Exception:  # noqa: BLE001
                    continue
                await self.handle(c, msg)
        except WebSocketDisconnect:
            pass
        except Exception as e:  # noqa: BLE001
            log.warning("ws fout: %s", e)
        finally:
            if c in self.clients:
                self.clients.remove(c)
            if c.kind == "player" and c.name:
                self.game.set_connected(c.name, -1)
                await self.broadcast()


def create_app(hub: Hub | None = None) -> FastAPI:
    app = FastAPI(title="Weerwolven van Wakkerdam")
    app.state.hub = hub or Hub()
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    @app.on_event("startup")
    async def _resume():
        # na een herstart: het laatste event alsnog vertellen als dat nog niet gebeurd was
        await app.state.hub.changed()

    @app.get("/")
    async def player_page():
        return FileResponse(STATIC / "player.html")

    @app.get("/screen")
    async def screen_page():
        return FileResponse(STATIC / "screen.html")

    @app.get("/host")
    async def host_page():
        return FileResponse(STATIC / "host.html")

    @app.get("/qr.svg")
    async def qr():
        import io
        buf = io.BytesIO()
        segno.make(app.state.hub.join_url(), error="m").save(buf, kind="svg", scale=8, dark="#f3e9d2", light=None, svgns=True, xmldecl=True)
        return Response(content=buf.getvalue(), media_type="image/svg+xml")

    @app.get("/api/state")
    async def api_state():
        return app.state.hub.game.public_view()

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await app.state.hub.ws_loop(ws)

    return app
