"""Regelgebaseerde interpretatie van vrije host-tekst.

Geeft een commando terug met een zekerheid. Bij lage zekerheid vraagt de
server het aan de LLM. Commando's:
  {"cmd": "advance"} | {"cmd": "repeat"} | {"cmd": "kill", "target": naam}
  {"cmd": "start_vote"} | {"cmd": "cancel_vote"} | {"cmd": "new_game"}
  {"cmd": "reset_seat", "target": naam} | {"cmd": "question", "text": ...}
  {"cmd": "unknown"}
"""
from __future__ import annotations

import difflib
import re
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


def find_names(text: str, names: list[str]) -> list[str]:
    """Namen in de tekst, in volgorde van voorkomen, met tolerantie voor typfouten."""
    toks = _norm(text).split()
    found: list[tuple[int, str]] = []
    lowered = {_norm(n): n for n in names}
    for i, tok in enumerate(toks):
        if tok in lowered:
            found.append((i, lowered[tok]))
            continue
        if len(tok) >= 4:
            m = difflib.get_close_matches(tok, list(lowered), n=1, cutoff=0.8)
            if m:
                found.append((i, lowered[m[0]]))
    seen: list[str] = []
    for _, n in sorted(found):
        if n not in seen:
            seen.append(n)
    return seen


KILL_WORDS = ("dood", "gestorven", "gelyncht", "lynch", "opgehangen", "hangt", "vermoord", "sterft", "gestemd", "weggestemd", "schiet", "geschoten", "neergeschoten", "eruit", "er uit", "dead")
ADVANCE_WORDS = ("volgende", "verder", "ga door", "doorgaan", "nacht", "start", "begin", "klaar", "next", "ok", "oke", "okee", "ja")
REPEAT_WORDS = ("herhaal", "opnieuw", "nog eens", "nog een keer", "repeat", "zeg dat")
VOTE_WORDS = ("stemmen", "stemming", "stem ")
CANCEL_WORDS = ("annuleer", "annuleren", "stop de stemming", "cancel")
NEWGAME_WORDS = ("nieuw spel", "opnieuw beginnen", "herstart", "reset het spel", "nieuwe ronde")
RESET_WORDS = ("zetel", "vrijgeven", "reset", "ander toestel", "andere gsm", "nieuwe telefoon")
QUESTION_WORDS = ("hoeveel", "wie ", "wat ", "welke", "waarom", "wanneer", "?")


def parse(text: str, names: list[str], phase: str) -> dict:
    t = " " + _norm(text) + " "
    found = find_names(text, names)

    def has(words: tuple[str, ...]) -> bool:
        return any((" " + w + " " in t) or (w in t and len(w) > 5) for w in words)

    if has(NEWGAME_WORDS):
        return {"cmd": "new_game", "confidence": 0.9}
    if has(RESET_WORDS) and found:
        return {"cmd": "reset_seat", "target": found[0], "confidence": 0.8}
    if has(REPEAT_WORDS) and not found:
        return {"cmd": "repeat", "confidence": 0.9}
    if has(CANCEL_WORDS) and phase == "vote":
        return {"cmd": "cancel_vote", "confidence": 0.9}
    if has(KILL_WORDS) and found:
        # "de jager schiet op X" -> X; "Bram is dood" -> Bram; bij 2 namen met 'schiet': laatste
        target = found[-1] if (("schiet" in t or "schoten" in t) and len(found) > 1) else found[0]
        return {"cmd": "kill", "target": target, "confidence": 0.85 if len(found) == 1 else 0.6}
    if has(VOTE_WORDS) and phase == "day" and not found:
        return {"cmd": "start_vote", "confidence": 0.85}
    if "?" in text or has(QUESTION_WORDS):
        return {"cmd": "question", "text": text, "confidence": 0.6}
    if has(ADVANCE_WORDS) and not found:
        return {"cmd": "advance", "confidence": 0.8}
    if found and not has(KILL_WORDS):
        return {"cmd": "unknown", "confidence": 0.2, "names": found}
    return {"cmd": "unknown", "confidence": 0.1}


LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "cmd": {"type": "string", "enum": ["advance", "repeat", "kill", "start_vote", "cancel_vote", "new_game", "reset_seat", "question", "unknown"]},
        "target": {"type": ["string", "null"]},
        "answer": {"type": ["string", "null"], "description": "Bij 'question': antwoord van de verteller in 1 tot 2 zinnen. Bij 'unknown': wat je niet begreep."},
    },
    "required": ["cmd"],
}


def llm_prompt(text: str, names: list[str], phase: str, public_summary: str) -> str:
    return (
        "Je bent de spelleider-assistent van een fysiek spel Weerwolven van Wakkerdam. De host (die zelf meespeelt en dus "
        "geen geheime rollen mag kennen) typt een bericht. Zet het om in precies een commando.\n"
        f"Spelers: {', '.join(names)}. Huidige fase: {phase}.\n"
        f"Publieke stand: {public_summary}\n"
        "Commando's: advance (volgende stap / ga door / nacht in / start), repeat (herhaal de verteller), "
        "kill (iemand is dood: gelyncht, geschoten door de jager, of correctie; target = naam), start_vote, cancel_vote, "
        "new_game, reset_seat (iemand wil op een ander toestel inloggen; target = naam), question (host stelt een vraag over "
        "de publieke stand of de regels; geef 'answer' in het Nederlands, kort, en onthul nooit geheime informatie), unknown.\n"
        f"Bericht van de host: \"{text}\""
    )
