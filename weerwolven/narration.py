"""Vertellerstekst: scripttemplates (altijd beschikbaar) en promptbouw voor de LLM.

De LLM krijgt uitsluitend publieke informatie. Rollen van levende spelers
komen hier nooit in terecht.
"""
from __future__ import annotations

import random

from .engine import CAUSE_TEXT, NIGHT_PHASES, Game
from .personages import ROLE_INFO

STYLE = (
    "Je bent de verteller van een fysiek spel Weerwolven van Wakkerdam, gespeeld door negen vrienden rond een tafel "
    "in Vlaanderen. Schrijf in natuurlijk Nederlands (Vlaams mag doorschemeren, geen Hollandse uitdrukkingen). "
    "Toon: spannend, sfeervol, droog en een beetje humor. Niet cringe, geen emoji, geen uitroeptekens-overload, "
    "geen opsommingen, geen aanhalingstekens rond het verhaal. Spreek de spelers aan met hun voornaam en hun "
    "dorpstitel (bv. 'Bram de molenaar'). Spreek het dorp aan met 'jullie', nooit met 'u'. Verzin geen feiten over wie "
    "schuldig is en onthul nooit een rol die niet in de context staat. Gebruik NOOIT 'hij', 'zij', 'hem' of 'haar' "
    "voor een speler: herhaal de voornaam of gebruik 'die'. Hou je strikt aan het opgegeven maximum aantal woorden. "
    "De tekst wordt voorgelezen door een computerstem: korte zinnen, geen afkortingen, geen opmaak. "
    "Schrijf alleen verhaal; zeg nooit wat de spelers moeten doen of waar ze moeten kijken."
)

INTRO_FALLBACK = [
    "Welkom in Wakkerdam, een dorp tussen de rivier en het bos, waar de deuren vroeger nooit op slot gingen. "
    "Sinds een paar weken is dat anders. Er verdwijnen schapen, er klinkt gehuil uit het bos, en twee van jullie zijn niet wie ze zeggen dat ze zijn. "
    "Vanavond komt het erop aan.",
]

INSTRUCTIONS = {
    "intro": "Lees nu stil je rol en personage op je GSM. Laat niemand meekijken. Niemand sluit de ogen: alles gebeurt op je telefoon. Tik op Gelezen als je klaar bent.",
    "night_cupido": "Iedereen kijkt naar zijn GSM en tikt op iemand. Niet praten, niet meekijken.",
    "night_wolves": "Iedereen kijkt naar zijn GSM en tikt op iemand. Niet praten, niet meekijken.",
    "night_witch": "Iedereen tikt nog een keer op zijn GSM.",
    "morning": "Bespreek aan tafel wie verdacht is. De host start de stemming.",
    "hunter": "Jager, kies op je GSM wie je meeneemt.",
    "vote_start": "Stem nu op je GSM. Blanco mag ook.",
    "tie": "Stem opnieuw op je GSM, alleen tussen de genoemde namen.",
    "lynch": "De host laat zo de nacht vallen.",
    "no_lynch": "De host laat zo de nacht vallen.",
    "death_host": "",
    "end": "Alle rollen staan op het scherm. De host kan een nieuw spel starten.",
}


def instruction_text(kind: str, g: Game) -> str:
    if kind == "hunter_shot":
        return INSTRUCTIONS["morning"] if g.phase == "day" else (INSTRUCTIONS["lynch"] if g.phase == "dusk" else "")
    if kind in ("lynch", "no_lynch", "morning") and g.phase == "end":
        return ""
    if kind == "morning" and g.phase == "hunter":
        return ""
    return INSTRUCTIONS.get(kind, "")

NIGHT_FALLBACK = {
    "night_cupido": [
        "De eerste nacht valt over Wakkerdam. Cupido sluipt door het dorp en kiest twee harten die vanaf nu aan elkaar hangen.",
    ],
    "night_wolves": [
        "Het dorp slaapt, of doet alsof. De wolven sluipen door de straten en kiezen hun prooi. De ziener tuurt ondertussen in het donker naar een gezicht.",
        "Mist hangt over de Wakker. Ergens in het dorp openen twee paar ogen zich die niet horen te glinsteren. De wolven kiezen. De ziener kijkt.",
    ],
    "night_witch": [
        "De heks wordt wakker van een geur die niet in het dorp thuishoort. De drankjes staan klaar, de keuze is zwaar.",
        "In een keuken brandt nog een kaars. De heks weegt af wat vannacht de moeite waard is.",
    ],
}

MORNING_NONE = [
    "De zon komt op boven Wakkerdam. De haan kraait, de deuren gaan open, en tot ieders verbazing wordt iedereen wakker. "
    "Niemand is gestorven vannacht. Dat betekent niet dat niemand het geprobeerd heeft.",
]
MORNING_ONE = [
    "De zon komt op boven Wakkerdam, maar niet voor iedereen. {titel} werd vanmorgen gevonden, {cause}. "
    "Het dorp verzamelt op het plein. Wie heeft dit gedaan?",
    "De ochtendmist trekt op en onthult wat de nacht achterliet. {titel} is dood, {cause}. "
    "Het dorp staart naar elkaar. Iemand hier weet er meer van.",
]
MORNING_MANY = [
    "Een zware ochtend in Wakkerdam. {lijst} zijn dood. De klokken luiden lang. Het dorp heeft nu geen tijd meer te verliezen.",
]
LYNCH_FALLBACK = [
    "Het dorp heeft gesproken. {titel} wordt naar de grote eik gebracht en komt niet meer terug.",
    "Na lang wikken en wegen wijst het dorp naar {titel}. Het vonnis wordt zonder veel ceremonie voltrokken.",
]
NO_LYNCH_FALLBACK = [
    "Het dorp raakt er niet uit. Niemand wordt vandaag veroordeeld, en de avond valt met een onbehaaglijk gevoel.",
]
TIE_FALLBACK = [
    "Gelijkspel. Het dorp raakt er niet uit en moet opnieuw kiezen, tussen {lijst}.",
]
VOTE_START_FALLBACK = [
    "Het dorp verzamelt zich onder de grote eik. De tijd van praten is voorbij.",
    "De klok op de kerktoren slaat. Wakkerdam moet oordelen.",
]
HUNTER_FALLBACK = [
    "{titel} was de jager. Met een laatste krachtsinspanning grijpt de jager naar het geweer en zoekt een doelwit.",
]
HUNTER_SHOT_FALLBACK = [
    "Een schot galmt over het plein. De jager heeft {titel} geraakt. Ook {titel} valt.",
]
LOVER_FALLBACK = " {titel} kon het niet aanzien en stierf van verdriet."
DUSK_FALLBACK = [
    "De avond valt over Wakkerdam. De overlevenden gaan naar huis en doen de deur op slot, voor wat het waard is.",
]
END_FALLBACK = {
    "dorp": "Het is gedaan. De laatste wolf ligt op het plein en Wakkerdam haalt opgelucht adem. Het dorp heeft gewonnen.",
    "wolven": "Het is gedaan. Er zijn niet genoeg dorpelingen meer om de wolven tegen te houden. Vannacht huilt het bos van vreugde. De wolven hebben gewonnen.",
    "geliefden": "Het is gedaan. Van heel Wakkerdam blijven alleen twee geliefden over, een uit elk kamp. De liefde heeft gewonnen, tegen alle regels in.",
}


def _pick(rng: random.Random, options: list[str]) -> str:
    return rng.choice(options)


def _role_suffix(d: dict, g: Game) -> str:
    if g.settings.get("reveal_roles") and d.get("role"):
        return f" {d['name']} was {ROLE_INFO[d['role']]['naam'].lower()}."
    return ""


def deaths_sentence(died: list[dict], g: Game, rng: random.Random, templates_one: list[str], templates_many: list[str]) -> str:
    """Zinnen over een reeks doden, inclusief geliefdenketen."""
    primary = [d for d in died if d["cause"] != "liefdesverdriet"]
    lovers = [d for d in died if d["cause"] == "liefdesverdriet"]
    if not primary and lovers:
        primary, lovers = lovers, []
    if len(primary) == 1:
        d = primary[0]
        cause = CAUSE_TEXT.get(d["cause"], d["cause"])
        if d["cause"] in ("wolven", "vergif"):
            cause = "met sporen die niemand hardop wil benoemen"
        text = _pick(rng, templates_one).format(titel=d["titel"], cause=cause)
    else:
        lijst = " en ".join(d["titel"] for d in primary)
        text = _pick(rng, templates_many).format(lijst=lijst)
    for d in lovers:
        text += LOVER_FALLBACK.format(titel=d["titel"])
    for d in died:
        text += _role_suffix(d, g)
    return text


def fallback_text(kind: str, g: Game, rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    if kind == "intro":
        return _pick(rng, INTRO_FALLBACK)
    if kind in NIGHT_PHASES:
        return _pick(rng, NIGHT_FALLBACK[kind])
    if kind == "morning":
        died = g.last_deaths
        if not died:
            text = _pick(rng, MORNING_NONE)
        else:
            text = deaths_sentence(died, g, rng, MORNING_ONE, MORNING_MANY)
        gossip = g.gossip_log[-1]["target"] if g.gossip_log and g.gossip_log[-1]["day"] == g.day else None
        if gossip:
            text += f" In de kroeg fluistert men vooral over {g.titel(gossip)}."
        return text
    if kind == "lynch":
        res = g.last_vote_result or {}
        died = g.last_deaths
        text = deaths_sentence(died, g, rng, LYNCH_FALLBACK, MORNING_MANY) if died else _pick(rng, NO_LYNCH_FALLBACK)
        return text
    if kind == "no_lynch":
        return _pick(rng, NO_LYNCH_FALLBACK)
    if kind == "tie":
        tie = (g.last_vote_result or {}).get("tie") or []
        return _pick(rng, TIE_FALLBACK).format(lijst=" en ".join(tie))
    if kind == "hunter":
        return _pick(rng, HUNTER_FALLBACK).format(titel=g.titel(g.hunter_pending) if g.hunter_pending else "de jager")
    if kind == "hunter_shot":
        ev = next((e for e in reversed(g.events) if e["kind"] == "hunter_shot"), None)
        died = (ev or {}).get("deaths") or []
        if not died:
            return "Het schot van de jager mist."
        text = _pick(rng, HUNTER_SHOT_FALLBACK).format(titel=died[0]["titel"])
        for d in died[1:]:
            text += LOVER_FALLBACK.format(titel=d["titel"])
        for d in died:
            text += _role_suffix(d, g)
        return text
    if kind == "dusk":
        return _pick(rng, DUSK_FALLBACK)
    if kind == "vote_start":
        return _pick(rng, VOTE_START_FALLBACK)
    if kind == "end":
        text = END_FALLBACK.get(g.winner or "dorp", END_FALLBACK["dorp"])
        wolves = [n for n in g.names if g.players[n]["role"] == "weerwolf"]
        text += " De wolven waren " + " en ".join(wolves) + "."
        lovers = [n for n in g.names if g.players[n]["lover"]]
        if lovers:
            text += " De geliefden waren " + " en ".join(sorted(set(lovers))) + "."
        return text
    return ""


def uses_llm(kind: str) -> bool:
    """Enkel de vertelmomenten die het waard zijn om op te wachten."""
    return kind in ("intro", "morning", "lynch", "hunter_shot", "end")


def _public_context(g: Game) -> str:
    alive = g.alive()
    dead = [n for n in g.names if not g.players[n]["alive"]]
    lines = [
        f"Dag {g.day}. Levend ({len(alive)}): " + ", ".join(g.titel(n) for n in alive) + ".",
    ]
    if dead:
        parts = []
        for n in dead:
            p = g.players[n]
            rol = f", was {ROLE_INFO[p['role']]['naam'].lower()}" if g.settings.get("reveal_roles") else ""
            parts.append(f"{g.titel(n)} (dag {p['died_day']}, {CAUSE_TEXT.get(p['death_cause'], p['death_cause'])}{rol})")
        lines.append("Dood: " + "; ".join(parts) + ".")
    recent = [c for c in g.chat["public"][-6:]]
    if recent:
        lines.append("Recente publieke berichten: " + " | ".join(f"{c['from']}: {c['text']}" for c in recent))
    return "\n".join(lines)


def build_prompt(kind: str, g: Game, fallback: str) -> str:
    """Prompt met uitsluitend publieke info. 'fallback' toont de feiten die zeker vermeld moeten worden."""
    ctx = _public_context(g)
    if kind == "intro":
        titels = "; ".join(f"{n}: {g.personage_of(n)['titel']}, {g.personage_of(n)['beroep']}" for n in g.names)
        task = (
            "Schrijf de openingstekst van het spel (maximaal 130 woorden). Beschrijf het dorp Wakkerdam en de dreiging: "
            "er zijn twee weerwolven onder de negen dorpelingen. Noem de dorpelingen met voornaam en titel: " + titels + ". "
            "Geen praktische instructies (die worden apart getoond): alleen sfeer en dreiging."
        )
    elif kind == "morning":
        died = g.last_deaths
        gossip = g.gossip_log[-1]["target"] if g.gossip_log and g.gossip_log[-1]["day"] == g.day else None
        facts = []
        if not died:
            facts.append("Niemand is vannacht gestorven.")
        for d in died:
            if d["cause"] == "liefdesverdriet":
                facts.append(f"{d['titel']} stierf daarna van liefdesverdriet (was dus verliefd op het vorige slachtoffer).")
            else:
                facts.append(f"{d['titel']} werd dood gevonden. De doodsoorzaak blijft vaag (zeg niet of het wolven of gif was).")
            if g.settings.get("reveal_roles"):
                facts.append(f"Onthul: {d['name']} was {ROLE_INFO[d['role']]['naam'].lower()}.")
        if gossip:
            facts.append(f"Sfeerdetail: het dorp roddelde vannacht vooral over {g.titel(gossip)} (zeg dit luchtig, het bewijst niets).")
        task = (
            "Schrijf de ochtendtekst (maximaal 90 woorden). Verwerk ALLE volgende feiten, verzin er geen bij:\n- "
            + "\n- ".join(facts)
            + "\nGebruik de publieke achtergrond van het personage (beroep) voor sfeer, bv. waar het lichaam gevonden werd. "
            "Sluit af met een aansporing dat het dorp nu moet bespreken."
        )
    elif kind == "lynch":
        died = g.last_deaths
        res = g.last_vote_result or {}
        facts = []
        if not died:
            facts.append("Het dorp kon niet beslissen; niemand werd vandaag veroordeeld.")
        for d in died:
            if d["cause"] == "liefdesverdriet":
                facts.append(f"{d['titel']} stierf meteen daarna van liefdesverdriet (was verliefd op de veroordeelde).")
            else:
                facts.append(f"Het dorp heeft {d['titel']} veroordeeld en ter dood gebracht" + (f" met {res['counts'].get(d['name'], '?')} stemmen." if res.get("counts") else "."))
            if g.settings.get("reveal_roles"):
                facts.append(f"Onthul: {d['name']} was {ROLE_INFO[d['role']]['naam'].lower()}. Reageer daar kort op (opluchting of een pijnlijke vergissing).")
        task = "Schrijf de tekst na de stemming (maximaal 60 woorden). Verwerk ALLE feiten, verzin er geen bij:\n- " + "\n- ".join(facts)
    elif kind == "hunter_shot":
        ev = next((e for e in reversed(g.events) if e["kind"] == "hunter_shot"), {})
        died = ev.get("deaths") or []
        facts = [f"De jager ({g.titel(ev.get('shooter')) if ev.get('shooter') else 'de jager'}) schoot in een laatste adem op {died[0]['titel'] if died else 'niemand'}."]
        for d in died[1:]:
            facts.append(f"{d['titel']} stierf daarna van liefdesverdriet.")
        if g.settings.get("reveal_roles"):
            for d in died:
                facts.append(f"Onthul: {d['name']} was {ROLE_INFO[d['role']]['naam'].lower()}.")
        task = "Schrijf de tekst over het schot van de jager (maximaal 50 woorden). Feiten:\n- " + "\n- ".join(facts)
    elif kind == "end":
        wolves = [g.titel(n) for n in g.names if g.players[n]["role"] == "weerwolf"]
        lovers = sorted({n for n in g.names if g.players[n]["lover"]})
        facts = [f"Winnaar: {g.winner}.", "De wolven waren " + " en ".join(wolves) + "."]
        if lovers:
            facts.append("De geliefden waren " + " en ".join(lovers) + ".")
        facts.append("Alle rollen: " + ", ".join(f"{n} {ROLE_INFO[g.players[n]['role']]['naam'].lower()}" for n in g.names) + ".")
        task = "Schrijf het slot van het spel (maximaal 110 woorden): wie won en waarom, een knipoog naar het verloop, en noem de wolven en de geliefden. Feiten:\n- " + "\n- ".join(facts)
    else:
        task = f"Schrijf een korte sfeertekst (2 zinnen) voor het moment '{kind}'. Basis: {fallback}"
    return f"{STYLE}\n\nSTAND VAN HET SPEL (publieke info):\n{ctx}\n\nOPDRACHT:\n{task}\n\nAntwoord met enkel de voor te lezen tekst."
