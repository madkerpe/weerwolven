"""Echte sonnet-test van de verteller (buiten pytest). uv run python scripts/llm_check.py"""
import asyncio, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
from weerwolven.engine import Game
from weerwolven import narration, llm, hostparse
from conftest import do_night, do_vote, roles

LIMITS = {"intro": 130, "morning": 90, "lynch": 60, "hunter_shot": 50, "end": 110}

async def tell(kind, g):
    fb = narration.fallback_text(kind, g)
    t = time.time()
    out = await llm.ask(narration.build_prompt(kind, g, fb))
    dt = time.time() - t
    words = len((out or "").split())
    pron = re.findall(r"\b(hij|zij|hem|haar|ze)\b", out or "", flags=re.I)
    print(f"\n=== {kind}: {dt:.1f}s, {words} woorden (max {LIMITS[kind]}), voornaamwoorden: {len(pron)}, 'u' gebruikt: {bool(re.search(r'\\bu\\b', out or ''))}")
    print(out if out else f"(geen antwoord, fallback zou zijn:) {fb}")

async def main():
    g = Game(seed=8); g.start_game()
    for n in g.names: g.ack_reveal(n)
    r = roles(g)
    print("claude beschikbaar:", llm.available(), "| model:", llm.MODEL, "| timeout:", llm.TIMEOUT)
    await tell("intro", g)
    # nacht 1: wolven doden burger 0, die verliefd is op de jager -> jager sterft van verdriet en schiet
    do_night(g, wolf_target=r["burger"][0], lovers=[r["burger"][0], r["jager"][0]])
    assert g.phase == "hunter"
    g.submit_hunter(r["jager"][0], r["weerwolf"][0])
    await tell("morning", g)
    await tell("hunter_shot", g)
    do_vote(g, r["weerwolf"][1])
    await tell("lynch", g)
    assert g.phase == "end", g.phase
    await tell("end", g)
    summ = narration._public_context(g)
    for txt in ["wie heeft er gewonnen en waarom?", "Stef was eigenlijk niet dood, we hadden ons vergist", "zet de wolven even stil"]:
        t = time.time(); res = await llm.ask(hostparse.llm_prompt(txt, g.names, g.phase, summ), schema=hostparse.LLM_SCHEMA, timeout=40)
        print(f"\n[host-tekst] {txt!r} -> {time.time()-t:.1f}s {res}")

asyncio.run(main())
