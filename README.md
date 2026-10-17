# Weerwolven van Wakkerdam - met automatische verteller

Een lokale webapp voor een fysieke avond Weerwolven met 9 spelers en zonder menselijke verteller.
De laptop in het midden is het hoofdscherm dat het verhaal vertelt (Nederlandse stem). Iedereen
speelt mee via de GSM op hetzelfde wifi-netwerk. Niemand hoeft de ogen te sluiten: alle nachtacties
gebeuren stil op de telefoon.

## Starten

```bash
cd ~/Personal/weerwolven
uv run python -m weerwolven            # poort 8000
```

De terminal print drie links:

| Wie | Link | Wat |
|---|---|---|
| Spelers | `http://<lan-ip>:8000/` | naam kiezen, rol lezen, nachtacties, stemmen, chatten |
| Hoofdscherm | `http://localhost:8000/screen` | verhaal, stem, wie leeft, QR-code. Zet dit in Chrome op volledig scherm |
| Host | `http://<lan-ip>:8000/host?key=XXXX` | knoppen en vrije tekst. Werkt ook op je eigen GSM |

Op het hoofdscherm klik je een keer op "Start de avond" (dat ontgrendelt het geluid). De stem is
Ellen (nl-BE) of Xander (nl-NL); je kunt wisselen rechtsonder.

## Verloop

1. **Wachtkamer**: iedereen scant de QR en kiest zijn naam. Een naam is daarna aan dat toestel gekoppeld.
2. **Rollen lezen**: host klikt "Start het spel". Iedereen leest op de GSM rol en personage en tikt "Gelezen".
3. **Nacht**: in twee (de eerste nacht drie) stappen krijgt *iedereen* een prompt op de GSM. Wie niets te
   doen heeft tikt "wie vertrouw je het minst" (dorpsgeroddel). Zo ziet niemand wie echt aan zet is.
   Cupido, dan wolven + ziener samen, dan heks. De stap sluit automatisch als iedereen getikt heeft.
4. **Ochtend**: de verteller vertelt wie er dood is. Daarna bespreken aan tafel.
5. **Stemmen**: host klikt "Start de stemming" (of typt het). Iedereen stemt op de GSM. Gelijkspel = herstemming, tweede gelijkspel = niemand sterft.
6. **Avond**: host klikt "Laat de nacht vallen".
7. **Jager** sterft: die kiest op de GSM wie mee gaat (of host typt "de jager schiet op X").

Doden zien op hun GSM alle rollen en hebben een eigen chat. Wolven hebben een privéchat, geliefden ook.

## Host-tekst

In het hostpaneel kun je typen (of inspreken met het microfoontje):

- "Bram is dood", "we hebben gestemd op Louisa en ze hangt" -> vraagt bevestiging, dan sterft die speler
- "volgende", "laat de nacht vallen", "start de stemming", "herhaal"
- "geef de zetel van Ninke vrij" -> Ninke kan op een ander toestel inloggen
- vragen over de publieke stand ("hoeveel mensen leven er nog?") worden door de verteller beantwoord

Eenvoudige zinnen worden lokaal herkend. De rest gaat naar `claude -p` (sonnet, via je Claude-abonnement),
dat duurt 10 tot 20 seconden. De host speelt zelf mee en krijgt daarom nooit geheime info te zien.

## Verteller

Vaste Nederlandse teksten werken altijd. Als `claude` op het pad staat, schrijft sonnet sfeervollere
teksten voor intro, ochtend, lynch, jagersschot en slot (10 tot 20 s, het scherm toont intussen
"de verteller denkt na"). Lukt dat niet binnen 30 s, dan komt de vaste tekst.

- `WW_NO_LLM=1` schakelt de LLM uit.
- `WW_MODEL=sonnet` kiest het model. `WW_LLM_TIMEOUT=30` de wachttijd in seconden.
- `claude -p` werkt niet vanuit een Claude Code-sessie; start de server in een gewone terminal.

## Als er iets misgaat

- **Telefoon kwijt of leeg**: host klikt "zetel vrij" bij die naam, speler kiest de naam op een ander toestel.
- **Iemand tikt niet**: host klikt "Forceer deze nachtstap" of "Tel de stemmen nu".
- **Server herstart**: de stand staat in `state.json`, alles loopt gewoon door. Verwijder dat bestand voor een schone start.
- **Verkeerde uitslag**: host typt "X is dood" (bevestigen) of klikt "dood" bij de speler.
- **Wifi hapert**: de telefoon verbindt zelf opnieuw en haalt de stand op. Zorg dat laptop en GSM's op hetzelfde netwerk zitten en dat de macOS-firewall Python toelaat.

## Zelf testen

```bash
uv run pytest                                   # motor + server
uv run python scripts/simulate.py --games 300   # bots spelen volledige spellen
uv run python scripts/bots.py --skip Marijn     # 8 bots spelen mee op de draaiende server, jij bent Marijn
uv run python scripts/llm_check.py              # echte sonnet-teksten bekijken
```
