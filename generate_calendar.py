import json
import re
import unicodedata
from datetime import datetime, date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event


# ============================================================
# CONFIGURATION
# ============================================================

FIGHTERS_FILE = "combattants.json"
OUTPUT_FILE = "calendar.ics"

UFC_ICS = (
    "https://raw.githubusercontent.com/"
    "clarencechaan/ufc-cal/ics/UFC.ics"
)

MMA_CALENDAR_URL = (
    "https://next-fight.com/en/mma-calendar"
)

IJF_URLS = {
    "Teddy Riner":
        "https://www.ijf.org/athlete/385/results?results_rank_group=all",

    "Joan-Benjamin Gaba":
        "https://www.ijf.org/athlete/46709/results?results_rank_group=all"
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139 Safari/537.36"
    )
}


# ============================================================
# OUTILS
# ============================================================

def normalize(text):
    """Normalise un texte pour comparer les noms."""

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFD",
        text
    )

    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text
    )

    return " ".join(
        text.split()
    )


def load_fighters():

    with open(
        FIGHTERS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    fighters = []

    for category in (
        "mma",
        "judo"
    ):

        for fighter in data.get(
            category,
            []
        ):

            if fighter not in fighters:

                fighters.append(
                    fighter
                )

    return fighters


def find_fighter(
    text,
    fighters
):

    normalized_text = normalize(
        text
    )

    for fighter in fighters:

        normalized_fighter = normalize(
            fighter
        )

        if normalized_fighter in normalized_text:

            return fighter

    return None


def download(
    url
):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response


# ============================================================
# CALENDRIER DE BASE
# ============================================================

def create_calendar():

    calendar = Calendar()

    calendar.add(
        "prodid",
        "-//Calendrier Combattants Personnel//FR"
    )

    calendar.add(
        "version",
        "2.0"
    )

    calendar.add(
        "X-WR-CALNAME",
        "Mes Combats MMA & Judo"
    )

    calendar.add(
        "X-WR-CALDESC",
        "Combats et compétitions de mes sportifs préférés"
    )

    calendar.add(
        "X-WR-TIMEZONE",
        "Europe/Paris"
    )

    return calendar


# ============================================================
# UFC
# ============================================================

def add_ufc(
    calendar,
    fighters
):

    print()
    print("================================")
    print(" UFC")
    print("================================")

    count = 0

    try:

        response = download(
            UFC_ICS
        )

        source = Calendar.from_ical(
            response.content
        )

    except Exception as error:

        print(
            "Erreur UFC :",
            error
        )

        return 0

    for component in source.walk():

        if component.name != "VEVENT":
            continue

        summary = str(
            component.get(
                "SUMMARY",
                ""
            )
        )

        description = str(
            component.get(
                "DESCRIPTION",
                ""
            )
        )

        location = str(
            component.get(
                "LOCATION",
                ""
            )
        )

        url = str(
            component.get(
                "URL",
                ""
            )
        )

        searchable = "\n".join(
            [
                summary,
                description,
                location
            ]
        )

        fighter = find_fighter(
            searchable,
            fighters
        )

        if not fighter:
            continue

        event = Event()

        uid = str(
            component.get(
                "UID",
                f"ufc-{count}"
            )
        )

        event.add(
            "uid",
            f"mma-calendar-ufc-{uid}"
        )

        event.add(
            "summary",
            f"🥊 UFC — {summary}"
        )

        if component.get(
            "DTSTART"
        ):

            event.add(
                "dtstart",
                component.decoded(
                    "DTSTART"
                )
            )

        if component.get(
            "DTEND"
        ):

            event.add(
                "dtend",
                component.decoded(
                    "DTEND"
                )
            )

        text = [
            "⭐ COMBATTANT SUIVI",
            fighter,
            "",
            "Organisation : UFC",
            "",
            description
        ]

        if url:

            text.extend(
                [
                    "",
                    "Source :",
                    url
                ]
            )

        event.add(
            "description",
            "\n".join(text)
        )

        if location:

            event.add(
                "location",
                location
            )

        event.add(
            "categories",
            "MMA,UFC"
        )

        calendar.add_component(
            event
        )

        count += 1

        print(
            "✓",
            fighter,
            "-",
            summary
        )

    return count


# ============================================================
# MMA : PFL / ONE / KSW / ARES / AUTRES
# ============================================================

def get_mma_event_links():

    print()
    print("================================")
    print(" RECHERCHE DES ÉVÉNEMENTS MMA")
    print("================================")

    response = download(
        MMA_CALENDAR_URL
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    links = []

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link.get(
            "href"
        )

        text = link.get_text(
            " ",
            strip=True
        )

        if not href:
            continue

        full_url = urljoin(
            MMA_CALENDAR_URL,
            href
        )

        # On garde les liens qui semblent
        # être des pages d'événements.
        if (
            "/event" in full_url
            or "/events/" in full_url
            or "/mma/" in full_url
        ):

            links.append(
                (
                    full_url,
                    text
                )
            )

    # Suppression des doublons
    unique = {}

    for url, text in links:

        unique[url] = text

    print(
        f"{len(unique)} événement(s) trouvé(s)."
    )

    return list(
        unique.items()
    )


def extract_jsonld_date(
    soup
):

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        raw = script.string

        if not raw:
            continue

        try:

            data = json.loads(
                raw
            )

        except Exception:

            continue

        objects = []

        if isinstance(
            data,
            dict
        ):

            objects.append(
                data
            )

        elif isinstance(
            data,
            list
        ):

            objects.extend(
                data
            )

        for obj in objects:

            if not isinstance(
                obj,
                dict
            ):
                continue

            for key in (
                "startDate",
                "startTime"
            ):

                if obj.get(
                    key
                ):

                    return obj.get(
                        key
                    )

    return None


def parse_iso_date(
    value
):

    if not value:
        return None

    value = value.strip()

    try:

        if value.endswith(
            "Z"
        ):

            return datetime.fromisoformat(
                value[:-1]
                + "+00:00"
            )

        return datetime.fromisoformat(
            value
        )

    except Exception:

        pass

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M"
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                value,
                fmt
            )

        except Exception:

            continue

    return None


def detect_organization(text):
    normalized = normalize(text)

    # UFC en priorité
    if "ufc" in normalized:
        return "UFC"

    # ONE Championship
    if (
        "one championship" in normalized
        or "one friday fights" in normalized
        or "one fight night" in normalized
        or "one on prime" in normalized
    ):
        return "ONE Championship"

    # PFL
    if (
        "professional fighters league" in normalized
        or "pfl" in normalized
    ):
        return "PFL"

    # KSW
    if "ksw" in normalized:
        return "KSW"

    # ARES
    if (
        "ares fighting championship" in normalized
        or "ares fc" in normalized
        or "ares" in normalized
    ):
        return "ARES"

    # ACA
    if "aca" in normalized:
        return "ACA"

    # BRAVE
    if "brave cf" in normalized:
        return "BRAVE CF"

    # RIZIN
    if "rizin" in normalized:
        return "RIZIN"

    return "MMA"

def add_mma_events(
    calendar,
    fighters
):

    links = get_mma_event_links()

    count = 0

    today = date.today()

    for url, link_text in links:

        try:

            response = download(
                url
            )

        except Exception as error:

            print(
                "Erreur événement :",
                url,
                error
            )

            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        page_text = soup.get_text(
            " ",
            strip=True
        )

        # On ne s'intéresse qu'aux pages
        # contenant un de nos combattants.
        fighter = find_fighter(
            page_text,
            fighters
        )

        if not fighter:

            continue

        title = ""

        if soup.title:

            title = soup.title.get_text(
                " ",
                strip=True
            )

        if not title:

            title = link_text

        organization = detect_organization(
            page_text
            + " "
            + title
            + " "
            + link_text
        )

        # Date de l'événement
        date_value = extract_jsonld_date(
            soup
        )

        event_date = parse_iso_date(
            date_value
        )

        # Si la page ne donne pas de date
        # exploitable, on ne crée pas
        # un événement avec une mauvaise date.
        if event_date is None:

            print(
                "? Date inconnue :",
                fighter,
                title
            )

            continue

        # On ignore les événements
        # déjà passés.
        if event_date.date() < today:

            continue

        event = Event()

        safe_uid = re.sub(
            r"[^a-zA-Z0-9]+",
            "-",
            url
        )

        event.add(
            "uid",
            "mma-calendar-"
            + safe_uid
        )

        event.add(
            "summary",
            f"🥊 {organization} — {fighter}"
        )

        event.add(
            "dtstart",
            event_date
        )

        event.add(
            "description",
            "\n".join(
                [
                    "⭐ COMBATTANT SUIVI",
                    fighter,
                    "",
                    f"Organisation : {organization}",
                    "",
                    f"Événement : {title}",
                    "",
                    "Calendrier :",
                    url
                ]
            )
        )

        event.add(
            "url",
            url
        )

        event.add(
            "categories",
            f"MMA,{organization}"
        )

        calendar.add_component(
            event
        )

        count += 1

        print(
            "✓",
            organization,
            "-",
            fighter,
            "-",
            title
        )

    return count


# ============================================================
# JUDO / IJF
# ============================================================

def parse_ijf_date(
    text
):

    text = text.strip()

    formats = [
        "%d. %b %Y",
        "%d. %B %Y",
        "%d %b %Y",
        "%d %B %Y"
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                text,
                fmt
            ).date()

        except Exception:

            continue

    return None


def add_judo_events(
    calendar,
    fighters
):

    print()
    print("================================")
    print(" JUDO / IJF")
    print("================================")

    count = 0

    today = date.today()

    for fighter, url in IJF_URLS.items():

        if fighter not in fighters:

            continue

        try:

            response = download(
                url
            )

        except Exception as error:

            print(
                "Erreur IJF :",
                fighter,
                error
            )

            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # Recherche des tableaux
        # de compétitions.
        rows = soup.find_all(
            "tr"
        )

        seen = set()

        for row in rows:

            text = row.get_text(
                " ",
                strip=True
            )

            if not text:
                continue

            # Recherche d'une date
            # du type :
            # 28. Aug 2026
            match = re.search(
                r"(\d{1,2}\.\s+"
                r"[A-Za-zÀ-ÿ]+\s+"
                r"\d{4})",
                text
            )

            if not match:

                continue

            date_text = match.group(
                1
            )

            competition_date = parse_ijf_date(
                date_text
            )

            if competition_date is None:

                continue

            if competition_date < today:

                continue

            # Retire la date du texte
            competition_name = re.sub(
                re.escape(date_text),
                "",
                text
            ).strip()

            if not competition_name:

                continue

            key = (
                fighter,
                competition_date.isoformat(),
                competition_name
            )

            if key in seen:

                continue

            seen.add(
                key
            )

            event = Event()

            uid_text = re.sub(
                r"[^a-zA-Z0-9]+",
                "-",
                competition_name
            )

            event.add(
                "uid",
                (
                    "judo-calendar-"
                    + normalize(fighter)
                    + "-"
                    + competition_date.isoformat()
                    + "-"
                    + uid_text
                )
            )

            event.add(
                "summary",
                f"🥋 Judo — {fighter}"
            )

            event.add(
                "dtstart",
                competition_date
            )

            event.add(
                "description",
                "\n".join(
                    [
                        "⭐ JUDOKA SUIVI",
                        fighter,
                        "",
                        "Compétition :",
                        competition_name,
                        "",
                        "Source officielle IJF :",
                        url
                    ]
                )
            )

            event.add(
                "url",
                url
            )

            event.add(
                "categories",
                "Judo,IJF"
            )

            calendar.add_component(
                event
            )

            count += 1

            print(
                "✓ JUDO",
                "-",
                fighter,
                "-",
                competition_name,
                "-",
                competition_date
            )

    return count


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

def main():

    print()
    print("========================================")
    print(" CALENDRIER PERSONNEL MMA + JUDO")
    print("========================================")
    print()

    fighters = load_fighters()

    print(
        "Combattants surveillés :"
    )

    for fighter in fighters:

        print(
            " -",
            fighter
        )

    calendar = create_calendar()

    # --------------------------------------------------------
    # UFC
    # --------------------------------------------------------

    ufc_count = add_ufc(
        calendar,
        fighters
    )

    # --------------------------------------------------------
    # PFL + ONE + KSW + ARES + autres
    # --------------------------------------------------------

    mma_count = add_mma_events(
        calendar,
        fighters
    )

    # --------------------------------------------------------
    # JUDO
    # --------------------------------------------------------

    judo_count = add_judo_events(
        calendar,
        fighters
    )

    # --------------------------------------------------------
    # ÉCRITURE
    # --------------------------------------------------------

    with open(
        OUTPUT_FILE,
        "wb"
    ) as file:

        file.write(
            calendar.to_ical()
        )

    print()
    print("========================================")
    print(" TERMINÉ")
    print("========================================")

    print(
        f"UFC : {ufc_count}"
    )

    print(
        f"Autres MMA : {mma_count}"
    )

    print(
        f"Judo : {judo_count}"
    )

    print(
        f"TOTAL : "
        f"{ufc_count + mma_count + judo_count}"
    )

    print()
    print(
        "calendar.ics a été généré."
    )


if __name__ == "__main__":

    main()
