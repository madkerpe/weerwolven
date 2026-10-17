"""Personages van Wakkerdam.

Elk personage is genderneutraal geschreven (tweede persoon, geen voornaamwoorden)
zodat het bij elke speler past. 'publiek' mag aan tafel verteld worden,
'geheim' is iets persoonlijks dat NIETS met de spelrol te maken heeft, maar
waar je toch liever niet over praat. Zo heeft iedereen iets te verbergen.
"""

PERSONAGES = [
    {
        "id": "molenaar",
        "titel": "de molenaar",
        "beroep": "Molenaar",
        "publiek": (
            "Je molen staat op de heuvel en je ziet alles wat er op de weg naar het dorp gebeurt. "
            "Vorige week is er 's nachts een zak meel verdwenen uit je schuur. "
            "Je verdenkt niemand in het bijzonder, zeg je."
        ),
        "geheim": "Je hebt al drie maanden geen pacht betaald aan de burgemeester en hoopt dat niemand ernaar vraagt.",
    },
    {
        "id": "dokter",
        "titel": "de dorpsdokter",
        "beroep": "Dorpsdokter",
        "publiek": (
            "Je bent de enige in Wakkerdam die kan lezen wat er op een medicijnflesje staat. "
            "Afgelopen dinsdag werd je midden in de nacht geroepen bij de familie Verhaeghe, "
            "al wil je niet zeggen waarvoor."
        ),
        "geheim": "Je diploma komt van een school die je ooit zelf hebt uitgevonden. Het werkt meestal wel.",
    },
    {
        "id": "kroegbaas",
        "titel": "de kroegbaas",
        "beroep": "Uitbater van De Gouden Haan",
        "publiek": (
            "Je runt De Gouden Haan, de enige kroeg van het dorp. Je hoort alle roddels als eerste, en soms als enige. "
            "Zaterdagnacht zat er een vreemdeling aan de toog die bij het eerste hanengekraai verdween zonder te betalen."
        ),
        "geheim": "Je lengt het bier aan met regenwater sinds de oogst slecht was.",
    },
    {
        "id": "postbode",
        "titel": "de postbode",
        "beroep": "Postbode",
        "publiek": (
            "Je fietst elke ochtend langs alle huizen en weet wie brieven krijgt van wie. "
            "Gisteren vond je een envelop zonder afzender voor de burgemeester, met iets zwaars erin."
        ),
        "geheim": "Je leest al jaren stiekem de kaartjes die de burgemeester naar de weduwe Claeys stuurt.",
    },
    {
        "id": "koster",
        "titel": "de koster",
        "beroep": "Koster",
        "publiek": (
            "Je luidt de klokken, onderhoudt het kerkhof en sluit elke avond de kerkdeur. "
            "Deze week stonden er twee verse graven die je niet zelf gegraven hebt."
        ),
        "geheim": "Je slaapt al een tijdje in de kerk omdat je thuis de huur niet meer kunt betalen.",
    },
    {
        "id": "veearts",
        "titel": "de veearts",
        "beroep": "Veearts",
        "publiek": (
            "Alle koeien, varkens en honden van Wakkerdam kennen je. "
            "Sinds kort vind je om de paar dagen een schaap met merkwaardige beten in de wei van boer Daems."
        ),
        "geheim": "Je bent doodsbang voor honden, en niemand mag dat weten.",
    },
    {
        "id": "onderwijzer",
        "titel": "de onderwijzer",
        "beroep": "Onderwijzer",
        "publiek": (
            "Je geeft les in het enige klaslokaal van Wakkerdam, aan kinderen van zes tot veertien tegelijk. "
            "Vrijdag tekende een van de kleinsten een wolf op het bord en wilde niet zeggen waar het idee vandaan kwam."
        ),
        "geheim": "Op het oogstfeest was je zo dronken dat je je van de hele nacht niets herinnert. Je zult iets moeten verzinnen.",
    },
    {
        "id": "smid",
        "titel": "de smid",
        "beroep": "Smid",
        "publiek": (
            "Je hamert van 's ochtends vroeg tot 's avonds laat en hebt handen als kolenschoppen. "
            "Vorige week bestelde iemand bij jou een set zilveren nagels en betaalde contant. "
            "Je vond het vreemd, maar geld is geld."
        ),
        "geheim": "Je hebt het hek van het kerkhof gemaakt en het slot heeft nooit gewerkt. Je durft dat niet toe te geven.",
    },
    {
        "id": "kruidenier",
        "titel": "de kruidenier",
        "beroep": "Kruidenier",
        "publiek": (
            "Je hebt de kruidenierswinkel op de markt. Iedereen koopt bij jou, dus jij weet wie plots veel kaarsen, "
            "touw of rauw vlees koopt. En er is inderdaad iemand die dat sinds kort doet."
        ),
        "geheim": "Je weegt al jaren net iets te weinig af. Het is nog nooit iemand opgevallen.",
    },
    {
        "id": "nachtwaker",
        "titel": "de nachtwaker",
        "beroep": "Nachtwaker",
        "publiek": (
            "Je loopt elke nacht je ronde met een lantaarn en roept de uren. "
            "De laatste nachten hoorde je gehuil uit het bos, maar je bent niet gaan kijken."
        ),
        "geheim": "Je slaapt meestal vanaf middernacht in het wachthuisje. Je ronde bestaat eigenlijk niet.",
    },
    {
        "id": "veerman",
        "titel": "de veerman",
        "beroep": "Veerman over de Wakker",
        "publiek": (
            "Zonder jou komt niemand het dorp in of uit, tenzij door het bos. "
            "Twee nachten geleden hoorde je iemand zwemmen, en dat doet in oktober niemand voor zijn plezier."
        ),
        "geheim": "Je zet 's nachts soms mensen over voor dubbel geld en stelt dan geen vragen.",
    },
    {
        "id": "kaasmaker",
        "titel": "de kaasmaker",
        "beroep": "Kaasmaker",
        "publiek": (
            "Je kelder zit vol wielen die liggen te rijpen, en je ruikt daar permanent naar. "
            "Gisteren was een van je kelderdeuren opengebroken, maar er ontbrak geen kaas. Wat zocht de dader dan?"
        ),
        "geheim": "De prijs van je kaas ging omhoog omdat je in het geheim de helft inkoopt in het volgende dorp.",
    },
]

BY_ID = {p["id"]: p for p in PERSONAGES}

ROLE_INFO = {
    "weerwolf": {
        "naam": "Weerwolf",
        "team": "wolven",
        "uitleg": (
            "Je bent een weerwolf. Elke nacht kiezen jij en je medewolf samen een slachtoffer op jullie GSM. "
            "Overdag doe je alsof je een gewone dorpeling bent. Je wint als de wolven minstens even talrijk zijn als de rest."
        ),
    },
    "burger": {
        "naam": "Burger",
        "team": "dorp",
        "uitleg": (
            "Je bent een gewone burger van Wakkerdam. Je hebt geen speciale kracht, alleen je verstand en je stem. "
            "Luister, discussieer en help het dorp de wolven te ontmaskeren."
        ),
    },
    "ziener": {
        "naam": "Ziener",
        "team": "dorp",
        "uitleg": (
            "Je bent de ziener. Elke nacht kies je op je GSM een speler en zie je diens echte rol. "
            "Wees voorzichtig met wat je overdag vertelt: de wolven luisteren mee."
        ),
    },
    "heks": {
        "naam": "Heks",
        "team": "dorp",
        "uitleg": (
            "Je bent de heks. Je hebt twee drankjes voor het hele spel: een levensdrank die het slachtoffer van de wolven redt, "
            "en een gifdrank die iemand naar keuze doodt. Elke nacht zie je op je GSM wie de wolven kozen."
        ),
    },
    "jager": {
        "naam": "Jager",
        "team": "dorp",
        "uitleg": (
            "Je bent de jager. Als je sterft, op welke manier ook, neem je onmiddellijk iemand mee in de dood. "
            "Je kiest op je GSM wie."
        ),
    },
    "cupido": {
        "naam": "Cupido",
        "team": "dorp",
        "uitleg": (
            "Je bent cupido. In de eerste nacht kies je op je GSM twee spelers die verliefd worden op elkaar. "
            "Sterft de ene, dan sterft de andere van verdriet. Je mag jezelf kiezen. Daarna ben je een gewone burger."
        ),
    },
}
