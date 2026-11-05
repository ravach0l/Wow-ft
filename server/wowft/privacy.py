"""Freigaben: Was Gruppenmitglieder von einem Charakter sehen.

Level und XP sind immer sichtbar (sonst gäbe es nichts zu vergleichen). Alles andere
kann der Besitzer je Charakter ausblenden. Der Besitzer sieht seine eigenen Charaktere
immer vollständig. Die Prüfung passiert hier auf dem Server; ausgeblendete Daten
verlassen ihn gar nicht erst (API, Feed, Foto-Abruf, Discord).

Die Schlüssel stehen auch in `web/src/privacy.ts` (mit deutschen Bezeichnungen).
"""

from dataclasses import dataclass

from sqlalchemy.orm import object_session

from . import features
from .models import Character


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    default: bool


CATEGORIES: tuple[Category, ...] = (
    # Spielzeit und das daraus berechnete Tempo (XP/Std., Zeit bis zum Maximallevel)
    # hängen zusammen: Wer eines zeigt, verrät das andere. Für andere sichtbar nur bei
    # eingeschaltetem Rennen-Modus (siehe hidden_for).
    Category("pace", "Spielzeit und Tempo", True),
    Category("gold", "Gold", False),
    Category("zone", "Aufenthaltsort", True),
    Category("gear", "Ausrüstung", True),
    Category("skills", "Berufe", True),
    Category("reputation", "Ruf", True),
    Category("talents", "Talente", True),
    Category("materials", "Handwerksmaterialien", True),
    Category("deaths", "Tode", True),
    Category("bosses", "Boss-Kills", True),
    Category("photo", "Foto", True),
)
KEYS = frozenset(c.key for c in CATEGORIES)

# Feed-Ereignisse, die zu einer Kategorie gehören. Alle anderen (z. B. Level-Ups) sind immer sichtbar.
EVENT_CATEGORY = {
    "skill": "skills",
    "item": "gear",
    "reputation": "reputation",
    "death": "deaths",
    "boss": "bosses",
}


def shares(c: Character) -> dict[str, bool]:
    """Alle Kategorien mit ihrem aktuellen Wert (Standard, überschrieben durch die Einstellung)."""
    out = {cat.key: cat.default for cat in CATEGORIES}
    out.update({k: bool(v) for k, v in (c.share or {}).items() if k in KEYS and k != "gold"})
    out["gold"] = bool(c.gold_visible)  # Gold hat eine eigene, ältere Spalte
    return out


def _race_enabled(c: Character) -> bool:
    """Ist der Rennen-Modus an? Pro Anfrage nur einmal gelesen (die Sitzung gehört zur Anfrage)."""
    session = object_session(c)
    if session is None:
        return False  # im Zweifel verbergen
    if "race_enabled" not in session.info:
        session.info["race_enabled"] = features.enabled(session, "race")
    return session.info["race_enabled"]


def hidden_for(c: Character, viewer_id: int | None) -> frozenset[str]:
    """Kategorien, die `viewer_id` von diesem Charakter nicht sehen darf (Besitzer: keine).

    Spielzeit (und das daraus berechnete Tempo) wird für andere nur angezeigt, wenn der
    Rennen-Modus an ist; dort ist der Vergleich der Zweck. Sonst bleibt sie verborgen,
    auch wenn der Besitzer sie freigegeben hat.
    """
    if viewer_id is not None and c.user_id == viewer_id:
        return frozenset()
    hidden = {k for k, v in shares(c).items() if not v}
    if not _race_enabled(c):
        hidden.add("pace")
    return frozenset(hidden)


def is_shared(c: Character, key: str, viewer_id: int | None) -> bool:
    return key not in hidden_for(c, viewer_id)


def event_visible(c: Character, viewer_id: int | None, event_type: str) -> bool:
    category = EVENT_CATEGORY.get(event_type)
    return category is None or category not in hidden_for(c, viewer_id)


def hidden_event_types(c: Character, viewer_id: int | None) -> list[str]:
    hidden = hidden_for(c, viewer_id)
    return [t for t, category in EVENT_CATEGORY.items() if category in hidden]


def update(c: Character, changes: dict[str, bool]) -> None:
    """Übernimmt Änderungen; unbekannte Kategorien sind ein Fehler (ValueError)."""
    unknown = sorted(set(changes) - KEYS)
    if unknown:
        raise ValueError(f"Unbekannte Kategorie: {', '.join(unknown)}")
    current = dict(c.share or {})
    for key, value in changes.items():
        if key == "gold":
            c.gold_visible = bool(value)
        else:
            current[key] = bool(value)
    c.share = current  # neues Objekt zuweisen, damit SQLAlchemy die Änderung bemerkt
