"""Talent-Icons: Icon-Namen per Zauber-ID nachschlagen und Bilder zwischenspeichern.

Das Addon schickt je Talent die Zauber-ID (moderne Talentbäume) oder einen Icon-Pfad
(klassische API). Den Icon-Namen liefert Wowhead (`nether.wowhead.com/…/tooltip/spell/ID`),
das Bild dessen Bilderserver. Beides holt der Server einmal und speichert es; die
Browser der Nutzer fragen nur unseren Server (keine Anfragen an Dritte, kein Tracking).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path, PureWindowsPath
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import new_session
from .models import SpellIcon, now

log = logging.getLogger(__name__)

ICON_RE = re.compile(r"^[a-z0-9_]{2,100}$")
# Forever zuerst, dann die Classic-Datenbanken, zuletzt Retail. Icon-Namen sind über die
# Versionen gleich; spätere Talente (z. B. Genesis, Eclipse) kennt erst WotLK/Cata.
TOOLTIP_URLS = (
    "https://nether.wowhead.com/forever/tooltip/spell/{id}",
    "https://nether.wowhead.com/classic/tooltip/spell/{id}",
    "https://nether.wowhead.com/tbc/tooltip/spell/{id}",
    "https://nether.wowhead.com/wotlk/tooltip/spell/{id}",
    "https://nether.wowhead.com/cata/tooltip/spell/{id}",
    "https://nether.wowhead.com/tooltip/spell/{id}",
)
IMAGE_URL = "https://wow.zamimg.com/images/wow/icons/large/{name}.jpg"
MAX_IMAGE_BYTES = 200_000
RETRY_AFTER = 7 * 86400  # „nichts gefunden“ nach einer Woche erneut versuchen
MAX_LOOKUPS_PER_UPLOAD = 300
USER_AGENT = "wowft-server (Freundes-Tracker)"


def icon_from_path(icon: Any) -> str | None:
    """'Interface\\\\Icons\\\\Spell_Nature_Starfall' -> 'spell_nature_starfall'."""
    if not isinstance(icon, str) or not icon:
        return None
    name = PureWindowsPath(icon).name.lower()
    name = re.sub(r"\.(blp|tga|jpg|png)$", "", name)
    return name if ICON_RE.match(name) else None


def icon_url(name: str | None) -> str | None:
    return f"/api/icons/{name}.jpg" if name and ICON_RE.match(name) else None


def spell_ids(state: dict[str, Any]) -> set[int]:
    out = set()
    for tab in state.get("talents") or []:
        for t in tab.get("talents") or []:
            if isinstance(t.get("spell"), int):
                out.add(t["spell"])
    return out


def known_icons(session: Session, ids: set[int]) -> dict[int, str | None]:
    if not ids:
        return {}
    rows = session.scalars(select(SpellIcon).where(SpellIcon.spell_id.in_(ids)))
    return {r.spell_id: r.icon for r in rows}


def missing(session: Session, ids: set[int]) -> list[int]:
    """Zauber-IDs ohne Eintrag oder mit altem „nichts gefunden“."""
    if not ids:
        return []
    rows = {r.spell_id: r for r in session.scalars(select(SpellIcon).where(SpellIcon.spell_id.in_(ids)))}
    cutoff = now() - RETRY_AFTER
    todo = [i for i in ids if i not in rows or (rows[i].icon is None and rows[i].checked < cutoff)]
    return sorted(todo)[:MAX_LOOKUPS_PER_UPLOAD]


def with_icons(session: Session, talents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ergänzt jeden Talent-Eintrag um iconUrl (oder None)."""
    ids = {t["spell"] for tab in talents for t in tab.get("talents") or [] if isinstance(t.get("spell"), int)}
    names = known_icons(session, ids)
    out = []
    for tab in talents:
        rows = []
        for t in tab.get("talents") or []:
            name = names.get(t.get("spell")) if isinstance(t.get("spell"), int) else None
            rows.append({**t, "iconUrl": icon_url(name or icon_from_path(t.get("icon")))})
        out.append({**tab, "talents": rows})
    return out


# --- Abfragen bei Wowhead ---------------------------------------------------------


def fetch_icon_name(client: httpx.Client, spell_id: int) -> str | None:
    for url in TOOLTIP_URLS:
        try:
            r = client.get(url.format(id=spell_id))
        except httpx.HTTPError as e:
            log.warning("Icon-Abfrage für Zauber %s fehlgeschlagen: %s", spell_id, e)
            raise
        if r.status_code != 200:
            continue
        try:
            name = r.json().get("icon")
        except ValueError:
            continue
        if isinstance(name, str) and ICON_RE.match(name.lower()):
            return name.lower()
    return None


def resolve_spells(ids: list[int]) -> None:
    """Hintergrundaufgabe nach einem Upload: Icon-Namen holen und speichern."""
    if not ids or not get_settings().icon_lookup:
        return
    with new_session() as session, httpx.Client(timeout=5, headers={"User-Agent": USER_AGENT}) as client:
        for spell_id in ids:
            try:
                name = fetch_icon_name(client, spell_id)
            except httpx.HTTPError:
                return  # Netz weg: beim nächsten Upload erneut
            row = session.get(SpellIcon, spell_id) or SpellIcon(spell_id=spell_id)
            row.icon, row.checked = name, now()
            session.merge(row)
            session.commit()


def icon_file(name: str) -> Path | None:
    """Pfad zum zwischengespeicherten Bild; lädt es beim ersten Mal herunter."""
    if not ICON_RE.match(name):
        return None
    folder = Path(get_settings().data_dir) / "icons"
    path = folder / f"{name}.jpg"
    if path.is_file():
        return path
    if not get_settings().icon_lookup:
        return None
    try:
        r = httpx.get(IMAGE_URL.format(name=name), timeout=5, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError as e:
        log.warning("Icon %s nicht geladen: %s", name, e)
        return None
    data = r.content
    if r.status_code != 200 or not data.startswith(b"\xff\xd8\xff") or len(data) > MAX_IMAGE_BYTES:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path
