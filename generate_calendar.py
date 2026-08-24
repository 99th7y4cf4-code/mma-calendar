import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import requests
from icalendar import Calendar, Event


# ============================================================
# CONFIGURATION
# ============================================================

UFC_CALENDAR_URL = (
    "https://raw.githubusercontent.com/"
    "clarencechaan/ufc-cal/ics/UFC.ics"
)

OUTPUT_FILE = "calendar.ics"
FIGHTERS_FILE = "combattants.json"


# ============================================================
# OUTILS
# ============================================================

def normalize(text):
    """
    Transforme un texte pour faciliter la comparaison des noms.
    Exemple :
    Benoît Saint Denis -> benoit saint denis
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFD", text)

    text = "".join(
        character
        for character in text
        if unicodedata.category(character) != "Mn"
    )

    text = text.lower()

    text = re.sub(r"[^a-z0-9]+", " ", text)

    return " ".join(text.split())


def load_fighters():
    """Charge les combattants depuis combattants.json."""

    with open(FIGHTERS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    fighters = []

    for category in ("mma", "judo"):
        for fighter in data.get(category, []):
            fighters.append(fighter)

    return fighters


def download_ufc_calendar():
    """Télécharge le calendrier UFC."""

    print("Téléchargement du calendrier UFC...")

    response = requests.get(
        UFC_CALENDAR_URL,
        timeout=30,
        headers={
            "User-Agent": "MMA-Calendar/1.0"
        }
    )

    response.raise_for_status()

    return response.content


def fighter_matches(text, fighters):
    """
    Vérifie si un des combattants préférés apparaît
    dans le texte de l'événement.
    """

    normalized_text = normalize(text)

    for fighter in fighters:
        normalized_fighter = normalize(fighter)

        if normalized_fighter in normalized_text:
            return fighter

    return None


# ============================================================
# CREATION DU CALENDRIER
# ============================================================

def create_calendar():
    fighters = load_fighters()

    print()
    print("Combattants surveillés :")

    for fighter in fighters:
        print(" -", fighter)

    print()

    source_data = download_ufc_calendar()

    source_calendar = Calendar.from_ical(source_data)

    output_calendar = Calendar()

    output_calendar.add(
        "prodid",
        "-//Calendrier MMA Personnel//FR"
    )

    output_calendar.add(
        "version",
        "2.0"
    )

    output_calendar.add(
        "X-WR-CALNAME",
        "Mes Combats MMA & Judo"
    )

    output_calendar.add(
        "X-WR-CALDESC",
        "Combats de mes combattants préférés"
    )

    output_calendar.add(
        "X-WR-TIMEZONE",
        "Europe/Paris"
    )

    number_of_events = 0

    # --------------------------------------------------------
    # PARCOURS DES EVENEMENTS UFC
    # --------------------------------------------------------

    for component in source_calendar.walk():

        if component.name != "VEVENT":
            continue

        summary = str(
            component.get("SUMMARY", "")
        )

        description = str(
            component.get("DESCRIPTION", "")
        )

        location = str(
            component.get("LOCATION", "")
        )

        url = str(
            component.get("URL", "")
        )

        # Toutes les informations de l'événement
        searchable_text = "\n".join(
            [
                summary,
                description,
                location,
            ]
        )

        matched_fighter = fighter_matches(
            searchable_text,
            fighters
        )

        # Si aucun de nos combattants n'est présent,
        # on ignore l'événement.
        if not matched_fighter:
            continue

        print(
            "Combat trouvé :",
            matched_fighter,
            "-",
            summary
        )

        new_event = Event()

        # ----------------------------------------------------
        # IDENTIFIANT
        # ----------------------------------------------------

        original_uid = str(
            component.get(
                "UID",
                f"mma-{number_of_events}"
            )
        )

        new_event.add(
            "uid",
            f"mma-calendar-{original_uid}"
        )

        # ----------------------------------------------------
        # TITRE
        # ----------------------------------------------------

        new_event.add(
            "summary",
            f"🥊 {summary}"
        )

        # ----------------------------------------------------
        # DATE / HEURE
        # ----------------------------------------------------

        if component.get("DTSTART"):

            start = component.decoded("DTSTART")

            new_event.add(
                "dtstart",
                start
            )

        if component.get("DTEND"):

            end = component.decoded("DTEND")

            new_event.add(
                "dtend",
                end
            )

        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        description_lines = [
            "⭐ COMBATTANT SUIVI",
            "",
            matched_fighter,
            "",
            "Organisation : UFC",
            "",
            "Carte complète :",
            description,
        ]

        if url:
            description_lines.extend(
                [
                    "",
                    "Source :",
                    url,
                ]
            )

        new_event.add(
            "description",
            "\n".join(description_lines)
        )

        # ----------------------------------------------------
        # LIEU
        # ----------------------------------------------------

        if location:
            new_event.add(
                "location",
                location
            )

        # ----------------------------------------------------
        # CATEGORIE
        # ----------------------------------------------------

        new_event.add(
            "categories",
            "MMA"
        )

        # ----------------------------------------------------
        # ALARMES
        # ----------------------------------------------------

        # Alerte 24 heures avant
        alarm_24h = Event()
        alarm_24h.add(
            "action",
            "DISPLAY"
        )
        alarm_24h.add(
            "description",
            f"🥊 Combat de {matched_fighter} demain"
        )
        alarm_24h.add(
            "trigger",
            timedelta(hours=-24)
        )

        # Alerte 1 heure avant
        alarm_1h = Event()
        alarm_1h.add(
            "action",
            "DISPLAY"
        )
        alarm_1h.add(
            "description",
            f"🥊 Combat de {matched_fighter} dans 1 heure"
        )
        alarm_1h.add(
            "trigger",
            timedelta(hours=-1)
        )

        # ----------------------------------------------------
        # AJOUT DES ALARMES
        # ----------------------------------------------------

        # Les alarmes seront ajoutées plus tard dans une
        # version spécialisée Apple Calendar.

        output_calendar.add_component(
            new_event
        )

        number_of_events += 1

    # ========================================================
    # ECRITURE DU FICHIER
    # ========================================================

    with open(
        OUTPUT_FILE,
        "wb"
    ) as file:

        file.write(
            output_calendar.to_ical()
        )

    print()
    print("----------------------------------------")
    print(
        f"{number_of_events} événement(s) ajouté(s)."
    )
    print(
        f"Calendrier créé : {OUTPUT_FILE}"
    )
    print("----------------------------------------")


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

if __name__ == "__main__":

    try:

        create_calendar()

    except Exception as error:

        print()
        print("ERREUR :")
        print(error)
        print()

        raise
