
import json
from datetime import datetime
from icalendar import Calendar

# Charger la liste des sportifs
with open("fighters.json", "r", encoding="utf-8") as f:
    fighters = json.load(f)

cal = Calendar()
cal.add("prodid", "-//MMA Calendar//FR")
cal.add("version", "2.0")

# Ce script crée pour l'instant un calendrier vide.
# Les événements seront ajoutés automatiquement dans les prochaines étapes.

with open("calendar.ics", "wb") as f:
    f.write(cal.to_ical())

print("calendar.ics généré avec succès")
