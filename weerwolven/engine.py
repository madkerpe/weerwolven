"""Spelmotor voor Weerwolven van Wakkerdam.

Pure toestandsmachine: geen IO, geen netwerk. De server roept methodes aan en
vraagt gefilterde views op per kijker (speler, scherm, host).

Fases:
  lobby -> reveal -> night_cupido (enkel nacht 1) -> night_wolves -> night_witch
        -> [hunter] -> day -> vote -> [hunter] -> dusk -> night_wolves ... -> end
"""
from __future__ import annotations

import random
import secrets
import time
from typing import Any

PLAYER_NAMES = ["Geike", "Griet", "Bram", "Louisa", "Ninke", "Leander", "Arnaud", "Stef", "Marijn"]
ROLE_DECK = ["weerwolf", "weerwolf", "burger", "burger", "burger", "ziener", "heks", "jager", "cupido"]

NIGHT_PHASES = ("night_cupido", "night_wolves", "night_witch")
ACTION_PHASES = NIGHT_PHASES + ("reveal", "vote", "hunter")

CAUSE_TEXT = {
    "wolven": "door de wolven",
    "vergif": "vergiftigd",
    "gelyncht": "door het dorp gelyncht",
    "jager": "neergeschoten door de jager",
    "liefdesverdriet": "gestorven van liefdesverdriet",
    "host": "door de verteller dood verklaard",
}


class GameError(Exception):
    """Fout met een boodschap die naar de speler/host mag."""


def _now() -> float:
    return time.time()


class Game:
    def __init__(self, names: list[str] | None = None, seed: int | None = None, personages: list[dict] | None = None):
        from .personages import PERSONAGES

        self.rng = random.Random(seed)
        self.personage_pool = personages or PERSONAGES
        self.names = list(names or PLAYER_NAMES)
        self.host_key = f"{self.rng.randrange(1000, 9999)}"
        self.settings = {"reveal_roles": True, "gossip": True}
        self.game_no = 0
        self.seats: dict[str, dict] = {n: {"token": None, "connected": 0} for n in self.names}
        self._fresh_game()

    # ------------------------------------------------------------------ setup
    def _fresh_game(self) -> None:
        self.phase = "lobby"
        self.day = 0
        self.players: dict[str, dict] = {
            n: {
                "role": None,
                "personage": None,
                "alive": True,
                "lover": None,
                "acked": False,
                "death_cause": None,
                "died_day": None,
            }
            for n in self.names
        }
        self.night: dict[str, Any] = {}
        self.witch_potions = {"heal": True, "poison": True}
        self.hunter_pending: str | None = None
        self.after_hunter: str | None = None
        self.vote: dict[str, Any] = {}
        self.last_vote_result: dict | None = None
        self.events: list[dict] = []
        self.narrations: list[dict] = []
        self.narr_batch = 0
        self.repeat = {"seq": 0, "id": None}
        self.chat: dict[str, list[dict]] = {"public": [], "wolves": [], "lovers": [], "dead": []}
        self.winner: str | None = None
        self.seer_log: list[dict] = []
        self.gossip_log: list[dict] = []
        self.last_deaths: list[dict] = []
        self.pending_confirm: dict | None = None
        self.version = 0
        self._event_id = 0
        self._narr_id = 0

    def new_game(self) -> None:
        """Zelfde spelers en zetels, alles anders opnieuw."""
        self._fresh_game()
        self.game_no += 1
        self._touch()

    def _touch(self) -> None:
        self.version += 1

    # --------------------------------------------------------------- helpers
    def alive(self) -> list[str]:
        return [n for n in self.names if self.players[n]["alive"]]

    def alive_with_role(self, role: str) -> list[str]:
        return [n for n in self.alive() if self.players[n]["role"] == role]

    def role_of(self, name: str) -> str | None:
        return self.players[name]["role"]

    def personage_of(self, name: str) -> dict | None:
        pid = self.players[name]["personage"]
        if not pid:
            return None
        return next(p for p in self.personage_pool if p["id"] == pid)

    def titel(self, name: str) -> str:
        p = self.personage_of(name)
        return f"{name} {p['titel']}" if p else name

    def _check_name(self, name: str) -> str:
        if name not in self.players:
            raise GameError(f"Onbekende speler: {name}")
        return name

    def _require_phase(self, *phases: str) -> None:
        if self.phase not in phases:
            raise GameError(f"Dat kan nu niet (fase: {self.phase}).")

    def _event(self, kind: str, text: str, **data: Any) -> dict:
        self._event_id += 1
        ev = {"id": self._event_id, "kind": kind, "text": text, "day": self.day, "phase": self.phase, "ts": _now(), **data}
        self.events.append(ev)
        return ev

    def add_narration(self, kind: str, text: str, status: str = "ready", event_id: int | None = None,
                      instruction: str | None = None, batch: int | None = None) -> dict:
        """Nieuwe vertellerstekst voor het scherm. 'text' is verhaal, 'instruction' is wat de spelers moeten doen.
        Items met dezelfde 'batch' horen bij hetzelfde moment en blijven samen op het scherm staan."""
        self._narr_id += 1
        if batch is None:
            self.narr_batch += 1
            batch = self.narr_batch
        item = {"id": self._narr_id, "kind": kind, "text": text, "status": status, "event_id": event_id,
                "instruction": instruction, "batch": batch, "day": self.day, "ts": _now()}
        self.narrations.append(item)
        self.narrations = self.narrations[-60:]
        self._touch()
        return item

    def update_narration(self, narr_id: int, text: str) -> bool:
        for item in self.narrations:
            if item["id"] == narr_id:
                item["text"] = text
                item["status"] = "ready"
                self._touch()
                return True
        return False

    def repeat_narration(self) -> None:
        ready = [n for n in self.narrations if n["status"] == "ready"]
        if not ready:
            raise GameError("Er is nog niets verteld.")
        self.repeat = {"seq": self.repeat["seq"] + 1, "id": ready[-1]["id"]}
        self._touch()

    # ----------------------------------------------------------------- seats
    def claim_seat(self, name: str, token: str | None, same_device: bool = False) -> str:
        self._check_name(name)
        seat = self.seats[name]
        if seat["token"] and same_device:
            return seat["token"]
        if seat["token"] and token != seat["token"]:
            raise GameError(f"{name} is al ingenomen op een ander toestel. Vraag de host om de zetel vrij te geven.")
        if not seat["token"]:
            seat["token"] = token or secrets.token_urlsafe(12)
            self._touch()
        return seat["token"]

    def check_token(self, name: str, token: str | None) -> bool:
        return name in self.seats and bool(token) and self.seats[name]["token"] == token

    def reset_seat(self, name: str) -> None:
        self._check_name(name)
        self.seats[name]["token"] = None
        self._touch()

    def set_connected(self, name: str, delta: int) -> None:
        if name in self.seats:
            self.seats[name]["connected"] = max(0, self.seats[name]["connected"] + delta)
            self._touch()

    # ------------------------------------------------------------ game start
    def start_game(self) -> None:
        self._require_phase("lobby")
        roles = list(ROLE_DECK)
        self.rng.shuffle(roles)
        pers = [p["id"] for p in self.personage_pool]
        self.rng.shuffle(pers)
        for i, n in enumerate(self.names):
            self.players[n]["role"] = roles[i]
            self.players[n]["personage"] = pers[i]
        self.phase = "reveal"
        self._event("start", "Het spel begint. Iedereen leest stil rol en personage op de GSM.")
        self._touch()

    def ack_reveal(self, name: str) -> None:
        self._require_phase("reveal")
        self._check_name(name)
        self.players[name]["acked"] = True
        self._touch()
        if all(self.players[n]["acked"] for n in self.alive()):
            self.begin_night()

    # ----------------------------------------------------------------- night
    def begin_night(self) -> None:
        self._require_phase("reveal", "dusk")
        self.day += 1
        self.night = {
            "wolf_votes": {},
            "wolf_target": None,
            "wolf_disagree": None,
            "seer_target": None,
            "seer_result": None,
            "witch": None,
            "gossip": {},
            "done": [],
            "lovers_set": False,
        }
        if self.day == 1 and self.alive_with_role("cupido"):
            self.phase = "night_cupido"
        else:
            self.phase = "night_wolves"
        self._event("night_step", f"Nacht {self.day} valt over Wakkerdam.", step=self.phase)
        self._touch()

    def _mark_done(self, name: str) -> None:
        if name not in self.night["done"]:
            self.night["done"].append(name)

    def night_progress(self) -> tuple[int, int]:
        return len([n for n in self.night.get("done", []) if self.players[n]["alive"]]), len(self.alive())

    def _night_step_complete(self) -> bool:
        return all(n in self.night["done"] for n in self.alive())

    def _advance_night_if_done(self) -> None:
        if not self._night_step_complete():
            return
        self._finish_night_step()

    def _finish_night_step(self) -> None:
        """Sluit de huidige nachtstap af (na alle bevestigingen of op bevel van de host)."""
        if self.phase == "night_cupido":
            if not self.night["lovers_set"]:
                cup = self.alive_with_role("cupido")
                if cup:
                    # host forceerde zonder keuze: kies willekeurig twee anderen
                    a, b = self.rng.sample(self.alive(), 2)
                    self._set_lovers(a, b)
            self.phase = "night_wolves"
            self.night["done"] = []
            self._event("night_step", "De wolven en de ziener zijn aan zet.", step=self.phase)
        elif self.phase == "night_wolves":
            wolves = self.alive_with_role("weerwolf")
            votes = {w: self.night["wolf_votes"].get(w) for w in wolves}
            targets = {t for t in votes.values() if t}
            if wolves and len(targets) != 1:
                if len(targets) > 1:
                    # wolven oneens: iedereen opnieuw, met melding
                    self.night["wolf_disagree"] = sorted(targets)
                    for w in wolves:
                        if w in self.night["done"]:
                            self.night["done"].remove(w)
                    self.night["wolf_votes"] = {}
                    self._touch()
                    return
                # geen enkele wolf koos (host forceerde): niemand sterft door wolven
                self.night["wolf_target"] = None
            else:
                self.night["wolf_target"] = next(iter(targets)) if targets else None
            if self.alive_with_role("heks"):
                self.phase = "night_witch"
                self.night["done"] = []
                self._event("night_step", "De heks is aan zet.", step=self.phase)
            else:
                self._resolve_night()
        elif self.phase == "night_witch":
            self._resolve_night()
        self._touch()

    def force_night_step(self) -> None:
        """Host: sluit de stap af, ook al heeft niet iedereen bevestigd."""
        self._require_phase(*NIGHT_PHASES)
        for n in self.alive():
            self._mark_done(n)
        # bij onenigheid tussen wolven: forceren = eerste stem telt
        if self.phase == "night_wolves":
            wolves = self.alive_with_role("weerwolf")
            votes = [self.night["wolf_votes"].get(w) for w in wolves if self.night["wolf_votes"].get(w)]
            if len(set(votes)) > 1:
                self.night["wolf_votes"] = {w: votes[0] for w in wolves}
        self._finish_night_step()

    def submit_gossip(self, name: str, target: str) -> None:
        """Decoy-actie voor wie niets te doen heeft: wie vertrouw je het minst?"""
        self._require_phase(*NIGHT_PHASES)
        self._check_name(name)
        self._check_name(target)
        if not self.players[name]["alive"]:
            raise GameError("Doden roddelen niet.")
        if target == name:
            raise GameError("Kies iemand anders dan jezelf.")
        self.night["gossip"][name] = target
        self._mark_done(name)
        self._touch()
        self._advance_night_if_done()

    def submit_cupido(self, name: str, a: str, b: str) -> None:
        self._require_phase("night_cupido")
        if self.role_of(name) != "cupido" or not self.players[name]["alive"]:
            raise GameError("Jij bent cupido niet.")
        self._check_name(a)
        self._check_name(b)
        if a == b:
            raise GameError("Kies twee verschillende spelers.")
        self._set_lovers(a, b)
        self._mark_done(name)
        self._touch()
        self._advance_night_if_done()

    def _set_lovers(self, a: str, b: str) -> None:
        self.players[a]["lover"] = b
        self.players[b]["lover"] = a
        self.night["lovers_set"] = True

    def submit_wolf(self, name: str, target: str) -> None:
        self._require_phase("night_wolves")
        if self.role_of(name) != "weerwolf" or not self.players[name]["alive"]:
            raise GameError("Jij bent geen weerwolf.")
        self._check_name(target)
        if not self.players[target]["alive"]:
            raise GameError(f"{target} is al dood.")
        if self.role_of(target) == "weerwolf":
            raise GameError("Wolven eten elkaar niet op.")
        self.night["wolf_votes"][name] = target
        self.night["wolf_disagree"] = None
        self._mark_done(name)
        self._touch()
        self._advance_night_if_done()

    def submit_seer(self, name: str, target: str) -> dict:
        self._require_phase("night_wolves")
        if self.role_of(name) != "ziener" or not self.players[name]["alive"]:
            raise GameError("Jij bent de ziener niet.")
        self._check_name(target)
        if target == name:
            raise GameError("Je kent je eigen rol al.")
        if self.night["seer_target"]:
            raise GameError("Je hebt vannacht al gekeken.")
        role = self.role_of(target)
        self.night["seer_target"] = target
        self.night["seer_result"] = role
        self.seer_log.append({"day": self.day, "target": target, "role": role})
        self._mark_done(name)
        self._touch()
        self._advance_night_if_done()
        return {"target": target, "role": role}

    def submit_witch(self, name: str, heal: bool = False, poison: str | None = None) -> None:
        self._require_phase("night_witch")
        if self.role_of(name) != "heks" or not self.players[name]["alive"]:
            raise GameError("Jij bent de heks niet.")
        if heal and not self.witch_potions["heal"]:
            raise GameError("Je levensdrank is op.")
        if heal and not self.night["wolf_target"]:
            raise GameError("Er is niemand om te redden.")
        if poison:
            self._check_name(poison)
            if not self.witch_potions["poison"]:
                raise GameError("Je gifdrank is op.")
            if not self.players[poison]["alive"]:
                raise GameError(f"{poison} is al dood.")
            if poison == name:
                raise GameError("Jezelf vergiftigen is geen plan.")
        self.night["witch"] = {"heal": bool(heal), "poison": poison}
        if heal:
            self.witch_potions["heal"] = False
        if poison:
            self.witch_potions["poison"] = False
        self._mark_done(name)
        self._touch()
        self._advance_night_if_done()

    def _resolve_night(self) -> None:
        witch = self.night.get("witch") or {}
        deaths: list[tuple[str, str]] = []
        target = self.night.get("wolf_target")
        if target and not witch.get("heal"):
            deaths.append((target, "wolven"))
        if witch.get("poison"):
            deaths.append((witch["poison"], "vergif"))
        died = self._apply_deaths(deaths)
        self.last_deaths = died
        gossip_top = self.gossip_summary()
        if gossip_top:
            self.gossip_log.append({"day": self.day, "target": gossip_top})
        names = ", ".join(d["name"] for d in died) if died else "niemand"
        self._event("morning", f"Ochtend van dag {self.day}. Dood: {names}.", deaths=died, gossip=gossip_top)
        self._after_deaths(next_phase="day")

    def gossip_summary(self) -> str | None:
        if not self.settings.get("gossip"):
            return None
        counts: dict[str, int] = {}
        for t in self.night.get("gossip", {}).values():
            counts[t] = counts.get(t, 0) + 1
        if not counts:
            return None
        best = max(counts.values())
        tops = [n for n, c in counts.items() if c == best]
        return tops[0] if len(tops) == 1 and best >= 2 else None

    # ---------------------------------------------------------------- deaths
    def _apply_deaths(self, deaths: list[tuple[str, str]]) -> list[dict]:
        """Past doden toe inclusief geliefdenketen. Jager wordt in de wacht gezet."""
        queue = list(deaths)
        died: list[dict] = []
        while queue:
            name, cause = queue.pop(0)
            p = self.players[name]
            if not p["alive"]:
                continue
            p["alive"] = False
            p["death_cause"] = cause
            p["died_day"] = self.day
            rec = {"name": name, "cause": cause, "role": p["role"], "titel": self.titel(name)}
            died.append(rec)
            self._event("death", f"{self.titel(name)} is dood ({CAUSE_TEXT.get(cause, cause)}).", name=name, cause=cause, role=p["role"])
            lover = p["lover"]
            if lover and self.players[lover]["alive"]:
                queue.append((lover, "liefdesverdriet"))
            if p["role"] == "jager":
                self.hunter_pending = name
        return died

    def _after_deaths(self, next_phase: str) -> None:
        """Na een reeks doden: eerst de jager laten schieten, dan winst controleren."""
        if self.hunter_pending:
            self.phase = "hunter"
            self.after_hunter = next_phase
            self._event("hunter", f"{self.titel(self.hunter_pending)} was de jager en mag nog een schot lossen.", name=self.hunter_pending)
            self._touch()
            return
        if self._check_win():
            return
        self.phase = next_phase
        if next_phase == "day":
            for n in self.names:
                self.players[n]["acked"] = False
        self._touch()

    def submit_hunter(self, name: str, target: str) -> None:
        self._require_phase("hunter")
        if name != self.hunter_pending:
            raise GameError("Jij bent de jager niet, of je bent al aan de beurt geweest.")
        self._check_name(target)
        if not self.players[target]["alive"]:
            raise GameError(f"{target} is al dood.")
        self.hunter_pending = None
        died = self._apply_deaths([(target, "jager")])
        self.last_deaths = self.last_deaths + died if self.after_hunter == "day" else died
        self._event("hunter_shot", f"De jager {name} schiet {self.titel(target)} neer.", shooter=name, target=target, deaths=died)
        self._after_deaths(next_phase=self.after_hunter or "day")

    def host_kill(self, target: str, cause: str = "host") -> list[dict]:
        """Host-override: iemand is dood (bv. fysiek gestemd, of correctie)."""
        self._check_name(target)
        if not self.players[target]["alive"]:
            raise GameError(f"{target} is al dood.")
        if self.phase in ("lobby", "end"):
            raise GameError("Er loopt geen spel.")
        died = self._apply_deaths([(target, cause)])
        self.last_deaths = died
        if self.phase in ("day", "vote"):
            self.vote = {}
            self.last_vote_result = {"lynched": target, "counts": {}, "round": 0, "override": True}
            self._event("lynch", f"{self.titel(target)} is gelyncht (gemeld door de host).", name=target, deaths=died)
            self._after_deaths(next_phase="dusk")
        elif self.phase == "hunter":
            # host meldt het schot van de jager
            self.hunter_pending = None
            self._event("hunter_shot", f"De jager schiet {self.titel(target)} neer (gemeld door de host).", target=target, deaths=died)
            self._after_deaths(next_phase=self.after_hunter or "day")
        else:
            self._event("death_host", f"{self.titel(target)} is dood verklaard door de host.", name=target, deaths=died)
            keep = self.phase if self.phase not in NIGHT_PHASES else self.phase
            self._after_deaths(next_phase=keep)
            if self.phase in NIGHT_PHASES:
                self._advance_night_if_done()
        return died

    # ------------------------------------------------------------------- day
    def start_vote(self) -> None:
        self._require_phase("day")
        self.vote = {"round": 1, "candidates": None, "votes": {}}
        self.phase = "vote"
        self._event("vote_start", "Het dorp stemt.")
        self._touch()

    def cancel_vote(self) -> None:
        self._require_phase("vote")
        self.vote = {}
        self.phase = "day"
        self._touch()

    def vote_candidates(self) -> list[str]:
        if self.vote.get("candidates"):
            return [c for c in self.vote["candidates"] if self.players[c]["alive"]]
        return self.alive()

    def submit_vote(self, name: str, target: str | None) -> None:
        self._require_phase("vote")
        self._check_name(name)
        if not self.players[name]["alive"]:
            raise GameError("Doden stemmen niet.")
        if target is not None:
            self._check_name(target)
            if target == name:
                raise GameError("Je kunt niet op jezelf stemmen.")
            if target not in self.vote_candidates():
                raise GameError(f"{target} staat niet op de stemlijst.")
        self.vote["votes"][name] = target
        self._touch()
        if all(n in self.vote["votes"] for n in self.alive()):
            self._tally()

    def force_vote(self) -> None:
        """Host: tel de stemmen die er zijn."""
        self._require_phase("vote")
        if not self.vote["votes"]:
            raise GameError("Nog niemand heeft gestemd.")
        self._tally()

    def _tally(self) -> None:
        votes = dict(self.vote["votes"])
        counts: dict[str, int] = {}
        for t in self.vote["votes"].values():
            if t:
                counts[t] = counts.get(t, 0) + 1
        if not counts:
            self.last_vote_result = {"lynched": None, "counts": {}, "round": self.vote["round"], "tie": [], "votes": votes}
            self._event("no_lynch", "Niemand kreeg stemmen. Niemand sterft.", counts=counts)
            self.vote = {}
            self.phase = "dusk"
            self._touch()
            return
        best = max(counts.values())
        tops = [n for n, c in counts.items() if c == best]
        if len(tops) == 1:
            target = tops[0]
            died = self._apply_deaths([(target, "gelyncht")])
            self.last_deaths = died
            self.last_vote_result = {"lynched": target, "counts": counts, "round": self.vote["round"], "votes": votes}
            self._event("lynch", f"Het dorp lyncht {self.titel(target)}.", name=target, counts=counts, deaths=died)
            self.vote = {}
            self._after_deaths(next_phase="dusk")
            return
        if self.vote["round"] == 1:
            self.vote = {"round": 2, "candidates": sorted(tops), "votes": {}}
            self.last_vote_result = {"lynched": None, "counts": counts, "round": 1, "tie": sorted(tops), "votes": votes}
            self._event("tie", "Gelijkspel. Herstemming tussen " + " en ".join(tops) + ".", tie=tops, counts=counts)
            self._touch()
            return
        self.last_vote_result = {"lynched": None, "counts": counts, "round": 2, "tie": sorted(tops), "votes": votes}
        self._event("no_lynch", "Opnieuw gelijkspel. Niemand sterft vandaag.", tie=tops, counts=counts)
        self.vote = {}
        self.phase = "dusk"
        self._touch()

    # --------------------------------------------------------------- winning
    def _check_win(self) -> bool:
        alive = self.alive()
        wolves = [n for n in alive if self.role_of(n) == "weerwolf"]
        others = [n for n in alive if self.role_of(n) != "weerwolf"]
        winner = None
        if len(alive) == 2 and self.players[alive[0]]["lover"] == alive[1]:
            teams = {("wolven" if self.role_of(n) == "weerwolf" else "dorp") for n in alive}
            if len(teams) == 2:
                winner = "geliefden"
        if winner is None:
            if not wolves:
                winner = "dorp"
            elif len(wolves) >= len(others):
                winner = "wolven"
        if winner:
            self.winner = winner
            self.phase = "end"
            self._event("end", f"Het spel is gedaan. Winnaar: {winner}.", winner=winner)
            self._touch()
            return True
        return False

    # ------------------------------------------------------------------ host
    def advance(self) -> str:
        """Host: 'volgende'. Doet in elke fase het voor de hand liggende."""
        if self.phase == "lobby":
            self.start_game()
        elif self.phase == "reveal":
            self.begin_night()
        elif self.phase in NIGHT_PHASES:
            self.force_night_step()
        elif self.phase == "day":
            self.start_vote()
        elif self.phase == "vote":
            self.force_vote()
        elif self.phase == "dusk":
            self.begin_night()
        elif self.phase == "hunter":
            raise GameError("De jager moet eerst schieten (of zeg: 'de jager schiet op X').")
        elif self.phase == "end":
            self.new_game()
        return self.phase

    def force_all_ack(self) -> None:
        self._require_phase("reveal")
        self.begin_night()

    # ------------------------------------------------------------------ chat
    def chat_channels(self, name: str) -> list[str]:
        p = self.players[name]
        chans = []
        if p["alive"]:
            chans.append("public")
        else:
            chans.append("dead")
        if p["role"] == "weerwolf" and p["alive"]:
            chans.append("wolves")
        if p["lover"] and p["alive"]:
            chans.append("lovers")
        return chans

    def post_chat(self, name: str, channel: str, text: str) -> None:
        self._check_name(name)
        text = (text or "").strip()[:280]
        if not text:
            raise GameError("Leeg bericht.")
        if channel not in self.chat_channels(name):
            raise GameError("Dat kanaal is niet voor jou.")
        self.chat[channel].append({"from": name, "text": text, "ts": _now(), "day": self.day, "phase": self.phase})
        self.chat[channel] = self.chat[channel][-200:]
        self._touch()

    # ---------------------------------------------------------------- prompts
    def prompt_for(self, name: str) -> dict:
        """Wat de telefoon van deze speler nu moet tonen (server-gestuurde UI)."""
        p = self.players[name]
        role = p["role"]
        alive = self.alive()
        others = [n for n in alive if n != name]
        if self.phase == "lobby":
            return {"kind": "wait", "title": "Wachten op de start", "text": "De host start het spel zodra iedereen er is."}
        if self.phase == "hunter" and name == self.hunter_pending:
            return {"kind": "pick", "title": "Jager: wie neem je mee?", "text": "Je sterft, maar je schiet nog een keer.", "options": others, "submitted": False}
        if not p["alive"]:
            return {"kind": "dead", "title": "Je bent dood", "text": "Blijf stil en geniet van het schouwspel. Je ziet nu alle rollen."}
        if self.phase == "reveal":
            return {"kind": "ack", "title": "Lees je rol en personage", "text": "Tik op 'Gelezen' als je klaar bent. Laat niemand meekijken.", "submitted": p["acked"]}
        if self.phase in NIGHT_PHASES:
            done = name in self.night["done"]
            if self.phase == "night_cupido" and role == "cupido":
                return {"kind": "pick2", "title": "Cupido: kies twee geliefden", "text": "Je mag jezelf kiezen.", "options": alive, "submitted": done}
            if self.phase == "night_wolves" and role == "weerwolf":
                mates = [w for w in self.alive_with_role("weerwolf") if w != name]
                info = {w: self.night["wolf_votes"].get(w) for w in mates}
                text = "Kies samen een slachtoffer. Jullie moeten dezelfde kiezen."
                if self.night.get("wolf_disagree"):
                    text = "Jullie kozen verschillend (" + " en ".join(self.night["wolf_disagree"]) + "). Kies opnieuw, dezelfde."
                return {
                    "kind": "pick",
                    "title": "Weerwolven: kies een slachtoffer",
                    "text": text,
                    "options": [n for n in others if self.role_of(n) != "weerwolf"],
                    "submitted": done,
                    "chosen": self.night["wolf_votes"].get(name),
                    "mates": info,
                }
            if self.phase == "night_wolves" and role == "ziener":
                if self.night["seer_target"]:
                    r = self.night["seer_result"]
                    from .personages import ROLE_INFO
                    return {"kind": "info", "title": "Ziener", "text": f"{self.night['seer_target']} is {ROLE_INFO[r]['naam']}.", "submitted": True}
                return {"kind": "pick", "title": "Ziener: wiens rol wil je zien?", "text": "", "options": others, "submitted": done}
            if self.phase == "night_witch" and role == "heks":
                victim = self.night["wolf_target"]
                return {
                    "kind": "witch",
                    "title": "Heks",
                    "text": (f"De wolven kozen {victim}." if victim else "De wolven hebben niemand gekozen."),
                    "victim": victim,
                    "can_heal": self.witch_potions["heal"] and bool(victim),
                    "can_poison": self.witch_potions["poison"],
                    "options": others,
                    "submitted": done,
                }
            # decoy voor iedereen zonder echte actie
            return {
                "kind": "pick",
                "title": "Wie vertrouw je het minst?",
                "text": "Iedereen tikt vannacht op iemand. Zo ziet niemand wie echt aan zet is.",
                "options": others,
                "submitted": done,
                "chosen": self.night["gossip"].get(name),
                "decoy": True,
            }
        if self.phase == "hunter":
            return {"kind": "wait", "title": "De jager richt...", "text": "Even geduld."}
        if self.phase == "day":
            return {"kind": "wait", "title": f"Dag {self.day}", "text": "Bespreek aan tafel wie verdacht is. De host start de stemming."}
        if self.phase == "vote":
            cands = [c for c in self.vote_candidates() if c != name]
            voted = name in self.vote.get("votes", {})
            title = "Stem" if self.vote.get("round") == 1 else "Herstemming"
            return {"kind": "vote", "title": title, "text": "Wie moet er vandaag hangen?", "options": cands, "submitted": voted, "chosen": self.vote.get("votes", {}).get(name), "allow_none": True}
        if self.phase == "dusk":
            return {"kind": "wait", "title": "Avond", "text": "De host laat straks de nacht vallen. Hou je GSM bij de hand."}
        if self.phase == "end":
            return {"kind": "end", "title": "Spel gedaan", "text": f"Winnaar: {self.winner}."}
        return {"kind": "wait", "title": "", "text": ""}

    # ------------------------------------------------------------------ views
    def _player_public(self, n: str) -> dict:
        p = self.players[n]
        show_role = (not p["alive"] and self.settings["reveal_roles"]) or self.phase == "end"
        return {
            "name": n,
            "alive": p["alive"],
            "connected": self.seats[n]["connected"] > 0,
            "claimed": bool(self.seats[n]["token"]),
            "titel": (self.personage_of(n) or {}).get("titel") if self.phase != "lobby" else None,
            "role": p["role"] if show_role else None,
            "death_cause": p["death_cause"],
            "died_day": p["died_day"],
            "acked": p["acked"] if self.phase == "reveal" else None,
            "lover": p["lover"] if self.phase == "end" else None,
        }

    def public_view(self) -> dict:
        done, total = self.night_progress() if self.phase in NIGHT_PHASES else (0, 0)
        voted = sorted(self.vote.get("votes", {}).keys()) if self.phase == "vote" else []
        return {
            "version": self.version,
            "game_no": self.game_no,
            "phase": self.phase,
            "day": self.day,
            "players": [self._player_public(n) for n in self.names],
            "alive_count": len(self.alive()),
            "night_progress": {"done": done, "total": total},
            "vote": {
                "round": self.vote.get("round"),
                "candidates": self.vote_candidates() if self.phase == "vote" else [],
                "voted": voted,
                "votes": dict(self.vote.get("votes", {})) if self.phase == "vote" else {},
                "last_result": self.last_vote_result,
            },
            "last_deaths": [{k: v for k, v in d.items() if k != "role" or self.settings["reveal_roles"]} for d in self.last_deaths],
            "hunter_pending": self.hunter_pending,
            "narrations": self.narrations[-12:],
            "repeat": self.repeat,
            "events": [e for e in self.events[-40:] if e["kind"] not in ("death",) or self.settings["reveal_roles"]],
            "chat": self.chat["public"][-30:],
            "winner": self.winner,
            "gossip": self.gossip_log[-1]["target"] if self.gossip_log and self.gossip_log[-1]["day"] == self.day else None,
            "settings": self.settings,
            "screen_instruction": self.screen_instruction(),
        }

    def screen_instruction(self) -> str:
        if self.phase == "lobby":
            return "Scan de QR-code en kies je naam."
        if self.phase == "reveal":
            return "Lees stil je rol en personage op je GSM. Tik daarna 'Gelezen'."
        if self.phase in NIGHT_PHASES:
            return "Nacht. Iedereen kijkt naar zijn GSM en tikt. Niet praten, niet meekijken."
        if self.phase == "hunter":
            return "De jager kiest op de GSM wie mee de dood in gaat."
        if self.phase == "day":
            return "Dag. Bespreek aan tafel. De host start de stemming."
        if self.phase == "vote":
            return "Stem op je GSM."
        if self.phase == "dusk":
            return "Avond. De host laat de nacht vallen."
        if self.phase == "end":
            return "Het spel is gedaan."
        return ""

    def player_view(self, name: str) -> dict:
        from .personages import ROLE_INFO

        self._check_name(name)
        p = self.players[name]
        view = self.public_view()
        me: dict[str, Any] = {
            "name": name,
            "alive": p["alive"],
            "role": p["role"],
            "role_info": ROLE_INFO.get(p["role"]) if p["role"] else None,
            "personage": self.personage_of(name),
            "lover": p["lover"],
            "prompt": self.prompt_for(name),
            "channels": self.chat_channels(name) if self.phase != "lobby" else [],
        }
        if p["role"] == "weerwolf":
            me["mates"] = [n for n in self.names if self.players[n]["role"] == "weerwolf" and n != name]
        if p["role"] == "ziener":
            me["seer_log"] = [{**e, "role_name": ROLE_INFO[e["role"]]["naam"]} for e in self.seer_log]
        if p["role"] == "heks":
            me["potions"] = dict(self.witch_potions)
        if not p["alive"] or self.phase == "end":
            me["all_roles"] = {n: self.players[n]["role"] for n in self.names}
            me["all_lovers"] = [n for n in self.names if self.players[n]["lover"]]
        view["me"] = me
        view["private_chat"] = {c: self.chat[c][-30:] for c in me["channels"] if c != "public"}
        return view

    def host_view(self) -> dict:
        view = self.public_view()
        view["host"] = {
            "pending_confirm": self.pending_confirm,
            "seats": {n: {"claimed": bool(s["token"]), "connected": s["connected"]} for n, s in self.seats.items()},
            "night_done": sorted(self.night.get("done", [])) if self.phase in NIGHT_PHASES else [],
            "actions": self.host_actions(),
            "witch_potions_left": None,  # bewust verborgen: host speelt mee
        }
        return view

    def host_actions(self) -> list[dict]:
        a = []
        ph = self.phase
        if ph == "lobby":
            a.append({"id": "start", "label": "Start het spel"})
        elif ph == "reveal":
            a.append({"id": "force_ack", "label": "Iedereen heeft gelezen, nacht in"})
        elif ph in NIGHT_PHASES:
            a.append({"id": "force_step", "label": "Forceer deze nachtstap"})
        elif ph == "day":
            a.append({"id": "start_vote", "label": "Start de stemming"})
        elif ph == "vote":
            a.append({"id": "force_vote", "label": "Tel de stemmen nu"})
            a.append({"id": "cancel_vote", "label": "Stemming annuleren"})
        elif ph == "dusk":
            a.append({"id": "night", "label": "Laat de nacht vallen"})
        elif ph == "end":
            a.append({"id": "new_game", "label": "Nieuw spel (zelfde spelers)"})
        a.append({"id": "repeat", "label": "Herhaal de verteller"})
        return a

    # ---------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        return {
            "names": self.names,
            "host_key": self.host_key,
            "settings": self.settings,
            "game_no": self.game_no,
            "seats": self.seats,
            "phase": self.phase,
            "day": self.day,
            "players": self.players,
            "night": self.night,
            "witch_potions": self.witch_potions,
            "hunter_pending": self.hunter_pending,
            "after_hunter": self.after_hunter,
            "vote": self.vote,
            "last_vote_result": self.last_vote_result,
            "events": self.events,
            "narrations": self.narrations,
            "narr_batch": self.narr_batch,
            "repeat": self.repeat,
            "chat": self.chat,
            "winner": self.winner,
            "seer_log": self.seer_log,
            "gossip_log": self.gossip_log,
            "last_deaths": self.last_deaths,
            "version": self.version,
            "_event_id": self._event_id,
            "_narr_id": self._narr_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Game":
        g = cls(names=d["names"])
        for k, v in d.items():
            setattr(g, k, v)
        g.pending_confirm = None
        for s in g.seats.values():
            s["connected"] = 0
        return g
