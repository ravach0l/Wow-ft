"""Ereignisse für den Feed: aus dem Addon (Level-Up, Tod, Boss) oder durch
Vergleich mit dem vorigen Stand abgeleitet (Beruf, Item, Ruf)."""

from __future__ import annotations

from typing import Any

SKILL_THRESHOLDS = (75, 150, 225, 300)
ITEM_MIN_QUALITY = 3  # selten (blau) und besser
REP_MIN_STANDING = 6  # ab Wohlwollend

SKILL_CATEGORIES = {
    "berufe": "profession",
    "professions": "profession",
    "sekundäre fertigkeiten": "secondary",
    "nebenberufe": "secondary",
    "secondary skills": "secondary",
    "waffenfertigkeiten": "weapon",
    "weapon skills": "weapon",
}

STANDINGS = {
    1: "Hasserfüllt",
    2: "Feindselig",
    3: "Unfreundlich",
    4: "Neutral",
    5: "Freundlich",
    6: "Wohlwollend",
    7: "Respektvoll",
    8: "Ehrfürchtig",
}

SLOTS = {
    1: "Kopf",
    2: "Hals",
    3: "Schultern",
    4: "Hemd",
    5: "Brust",
    6: "Taille",
    7: "Beine",
    8: "Füße",
    9: "Handgelenke",
    10: "Hände",
    11: "Finger",
    12: "Finger",
    13: "Schmuck",
    14: "Schmuck",
    15: "Rücken",
    16: "Waffenhand",
    17: "Schildhand",
    18: "Distanz",
    19: "Wappenrock",
}


def skill_category(header: str | None) -> str | None:
    return SKILL_CATEGORIES.get((header or "").strip().lower())


def derive(prev: dict[str, Any], new: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """Gibt (typ, key, daten) für Änderungen zwischen zwei Ständen zurück.

    Abschnitte, die es im vorigen Stand noch nicht gab, erzeugen keine
    Ereignisse – sonst würde der erste Upload den Feed fluten.
    """
    out: list[tuple[str, str, dict[str, Any]]] = []

    if "skills" in prev and "skills" in new:
        before = {s["name"]: s.get("rank") or 0 for s in prev["skills"]}
        for s in new["skills"]:
            if skill_category(s.get("header")) not in ("profession", "secondary"):
                continue
            old, rank = before.get(s["name"], 0), s.get("rank") or 0
            for th in SKILL_THRESHOLDS:
                if old < th <= rank:
                    out.append(("skill", f"{s['name']}:{th}", {"name": s["name"], "rank": th}))

    if "equipment" in prev and "equipment" in new:
        before = {e["slot"]: e.get("id") for e in prev["equipment"]}
        for e in new["equipment"]:
            good = (e.get("quality") or 0) >= ITEM_MIN_QUALITY
            if good and e.get("id") and before.get(e["slot"]) != e["id"]:
                data = {"name": e.get("name"), "id": e["id"], "quality": e["quality"], "slot": e["slot"]}
                out.append(("item", f"{e['slot']}:{e['id']}", data))

    if "reputation" in prev and "reputation" in new:
        before = {r.get("id") or r["name"]: r.get("standing") or 0 for r in prev["reputation"]}
        for r in new["reputation"]:
            key = r.get("id") or r["name"]
            standing = r.get("standing") or 0
            if standing >= REP_MIN_STANDING and standing > before.get(key, 0):
                out.append(("reputation", f"{key}:{standing}", {"name": r["name"], "standing": standing}))

    return out


def describe(type_: str, data: dict[str, Any] | None) -> str:
    d = data or {}
    if type_ == "level_up":
        return f"hat Level {d.get('level')} erreicht"
    if type_ == "skill":
        return f"hat {d.get('name')} auf {d.get('rank')} gebracht"
    if type_ == "item":
        return f"trägt jetzt [{d.get('name')}]"
    if type_ == "reputation":
        return f"ist bei {d.get('name')} jetzt {STANDINGS.get(d.get('standing'), d.get('standing'))}"
    if type_ == "death":
        where = f" in {d['zone']}" if d.get("zone") else ""
        return f"ist gestorben{where}"
    if type_ == "boss":
        where = f" ({d['instance']})" if d.get("instance") else ""
        return f"hat {d.get('name')} besiegt{where}"
    return type_
