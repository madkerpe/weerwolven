"""Bots die als echte spelers via de websocket meespelen. Handig om alleen te testen.

uv run python scripts/bots.py --url ws://localhost:8000/ws --skip Marijn
Bots kiezen alle namen behalve --skip, lezen hun prompt en handelen na een korte pauze.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random

import websockets

NAMES = ["Geike", "Griet", "Bram", "Louisa", "Ninke", "Leander", "Arnaud", "Stef", "Marijn"]


async def bot(url: str, name: str, delay: float, chatty: bool, log):
    rng = random.Random(hash(name) & 0xFFFF)
    token = None
    last_key = None
    claiming = False
    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                await ws.send(json.dumps({"type": "hello", "kind": "player", "name": name, "token": token}))
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg["type"] == "claimed":
                        token = msg["token"]
                        claiming = False
                        continue
                    if msg["type"] == "error":
                        log(f"{name}: fout: {msg['text']}")
                        if "ingenomen" in msg["text"]:
                            claiming = False  # opnieuw proberen zodra de host de zetel vrijgeeft
                            await asyncio.sleep(2)
                        continue
                    if msg["type"] == "kicked":
                        token = None
                        claiming = True
                        await ws.send(json.dumps({"type": "claim", "name": name}))
                        continue
                    if msg["type"] != "state":
                        continue
                    v = msg["view"]
                    if "me" not in v:
                        if not claiming:
                            claiming = True
                            await ws.send(json.dumps({"type": "claim", "name": name, "token": token}))
                        continue
                    me = v["me"]
                    p = me["prompt"]
                    key = (v["phase"], v["day"], p["kind"], p.get("submitted"), json.dumps(p.get("mates")), v.get("vote", {}).get("round"))
                    if key == last_key:
                        continue
                    last_key = key
                    act = None
                    opts = p.get("options") or []
                    if p["kind"] == "ack" and not p["submitted"]:
                        act = {"action": "ack"}
                    elif p["kind"] == "pick2" and not p["submitted"]:
                        a, b = rng.sample(opts, 2)
                        act = {"action": "cupido", "a": a, "b": b}
                    elif p["kind"] == "pick" and opts:
                        if p.get("decoy") and not p["submitted"]:
                            act = {"action": "gossip", "target": rng.choice(opts)}
                        elif v["phase"] == "hunter":
                            act = {"action": "hunter", "target": rng.choice(opts)}
                        elif me["role"] == "weerwolf" and v["phase"] == "night_wolves":
                            mates = [t for t in (p.get("mates") or {}).values() if t]
                            if not p["submitted"]:
                                act = {"action": "wolf", "target": mates[0] if mates else rng.choice(opts)}
                            elif mates and p.get("chosen") != mates[0]:
                                act = {"action": "wolf", "target": mates[0]}
                        elif me["role"] == "ziener" and not p["submitted"]:
                            act = {"action": "seer", "target": rng.choice(opts)}
                    elif p["kind"] == "witch" and not p["submitted"]:
                        heal = bool(p.get("can_heal")) and rng.random() < 0.5
                        poison = rng.choice(opts) if p.get("can_poison") and rng.random() < 0.3 else None
                        act = {"action": "witch", "heal": heal, "poison": poison}
                    elif p["kind"] == "vote" and not p["submitted"] and opts:
                        act = {"action": "vote", "target": opts[0] if rng.random() < 0.6 else rng.choice(opts)}
                    if act:
                        await asyncio.sleep(delay * (0.5 + rng.random()))
                        await ws.send(json.dumps({"type": "act", **act}))
                        log(f"{name} ({me['role']}): {act}")
                    if chatty and v["phase"] == "day" and rng.random() < 0.3 and me["alive"]:
                        await asyncio.sleep(delay)
                        await ws.send(json.dumps({"type": "chat", "channel": "public", "text": rng.choice(["Ik vertrouw het niet.", "Wie was er gisteren laat op?", "Ik ben gewoon burger, echt.", "Stem op wie het stilst is."])}))
        except Exception as e:  # noqa: BLE001
            log(f"{name}: verbinding weg ({e}), opnieuw...")
            await asyncio.sleep(1.5)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://localhost:8000/ws")
    ap.add_argument("--skip", nargs="*", default=["Marijn"], help="namen die een echte mens speelt")
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--chat", action="store_true")
    args = ap.parse_args()
    names = [n for n in NAMES if n not in args.skip]
    print("Bots:", ", ".join(names), flush=True)
    log = lambda s: print(s, flush=True)
    await asyncio.gather(*(bot(args.url, n, args.delay, args.chat, log) for n in names))


if __name__ == "__main__":
    asyncio.run(main())
