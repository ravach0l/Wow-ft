"""Nimmt SavedVariables entgegen und schreibt neue Snapshots/Ereignisse.

Doppelte Uploads sind harmlos: Snapshots sind über (Charakter, Zeitpunkt)
eindeutig, Ereignisse über (Charakter, Zeitpunkt, Typ, Schlüssel).
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from . import events, svparse
from .config import get_settings
from .models import Character, Event, Photo, Snapshot, User, now

SUPPORTED_SCHEMAS = {1}


class IngestError(ValueError):
    pass


def _empty_dict_to_list(v: Any) -> Any:
    # Lua kennt keinen Unterschied zwischen leerer Liste und leerem Dict.
    return [] if v == {} else v


class SnapshotIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    t: int = Field(gt=1_000_000_000)
    level: int = Field(ge=1, le=200)
    xp: int = Field(ge=0)
    xpMax: int = Field(ge=0)
    rested: int = Field(default=0, ge=0)
    zone: str | None = Field(default=None, max_length=100)
    playedTotal: int | None = Field(default=None, ge=0)
    playedLevel: int | None = Field(default=None, ge=0)
    gold: int | None = Field(default=None, ge=0)


class LevelUpIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    t: int = Field(gt=1_000_000_000)
    level: int = Field(ge=1, le=200)
    playedTotal: int | None = Field(default=None, ge=0)


class _In(BaseModel):
    model_config = ConfigDict(extra="ignore")


def LuaList(item: Any, max_length: int = 500) -> Any:  # noqa: N802
    """Liste, die aus Lua auch als leere Tabelle {} kommen darf."""
    return Annotated[list[item], BeforeValidator(_empty_dict_to_list), Field(max_length=max_length)]


class SkillIn(_In):
    name: str = Field(max_length=100)
    rank: int = Field(default=0, ge=0)
    max: int | None = Field(default=None, ge=0)
    header: str | None = Field(default=None, max_length=100)


class EquipIn(_In):
    slot: int = Field(ge=0, le=19)
    id: int | None = None
    name: str | None = Field(default=None, max_length=150)
    quality: int | None = Field(default=None, ge=0, le=8)


class RepIn(_In):
    id: int | None = None
    name: str = Field(max_length=100)
    standing: int = Field(default=4, ge=0, le=8)
    value: int | None = None
    min: int | None = None
    max: int | None = None


class TalentIn(_In):
    name: str = Field(max_length=100)
    rank: int = Field(ge=0)
    max: int | None = None
    tier: int | None = None
    col: int | None = None


class TalentTabIn(_In):
    name: str | None = Field(default=None, max_length=100)
    points: int = Field(default=0, ge=0)
    talents: LuaList(TalentIn, 250) = Field(default_factory=list)


class MaterialIn(_In):
    id: int
    name: str | None = Field(default=None, max_length=150)
    count: int = Field(ge=0)


class MaterialsIn(_In):
    bags: LuaList(MaterialIn) = Field(default_factory=list)
    bank: LuaList(MaterialIn) | None = None
    bankScanned: int | None = None


class DeathIn(_In):
    t: int = Field(gt=1_000_000_000)
    level: int | None = None
    zone: str | None = Field(default=None, max_length=100)


class BossIn(_In):
    t: int = Field(gt=1_000_000_000)
    id: int | None = None
    name: str = Field(max_length=150)
    instance: str | None = Field(default=None, max_length=150)
    level: int | None = None


class CharacterIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    guid: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    realm: str | None = Field(default=None, max_length=64)
    region: str | None = Field(default=None, max_length=8)
    class_: str | None = Field(default=None, alias="class", max_length=32)
    race: str | None = Field(default=None, max_length=32)
    faction: str | None = Field(default=None, max_length=16)
    snapshots: list[SnapshotIn] = Field(default_factory=list, max_length=500)
    levelUps: list[LevelUpIn] = Field(default_factory=list, max_length=500)
    # Phase 4 – alles optional, ältere Addon-Versionen schicken es nicht.
    deaths: int | None = Field(default=None, ge=0)
    deathLog: LuaList(DeathIn) = Field(default_factory=list)
    bossKills: LuaList(BossIn) = Field(default_factory=list)
    photoRequests: LuaList(int, 50) = Field(default_factory=list)
    skills: LuaList(SkillIn, 200) | None = None
    equipment: LuaList(EquipIn, 20) | None = None
    reputation: LuaList(RepIn, 200) | None = None
    talents: LuaList(TalentTabIn, 5) | None = None
    materials: MaterialsIn | None = None

    _lists = field_validator("snapshots", "levelUps", mode="before")(_empty_dict_to_list)

    def state(self) -> dict[str, Any]:
        """Die Teile, die als jüngster Stand am Charakter gespeichert werden."""
        out: dict[str, Any] = {}
        for key in ("skills", "equipment", "reputation", "talents"):
            value = getattr(self, key)
            if value is not None:
                out[key] = [v.model_dump() for v in value]
        if self.materials is not None:
            out["materials"] = self.materials.model_dump()
        if self.deaths is not None:
            out["deaths"] = self.deaths
        return out


class SavedVariablesIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_: int = Field(alias="schema")
    addonVersion: str | None = None
    characters: dict[str, CharacterIn] = Field(default_factory=dict)

    @field_validator("characters", mode="before")
    @classmethod
    def _chars(cls, v: Any) -> Any:
        return {} if v == [] else v


def decode(body: bytes, content_type: str | None) -> SavedVariablesIn:
    """Akzeptiert die rohe WowFT.lua oder bereits umgewandeltes JSON."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("latin-1")
    try:
        if content_type and "json" in content_type:
            data = json.loads(text)
            db = data.get("WowFTDB", data)
        else:
            db = svparse.parse(text).get("WowFTDB")
            if db is None:
                raise IngestError("WowFTDB fehlt in der Datei")
    except (svparse.ParseError, json.JSONDecodeError) as e:
        raise IngestError(f"Datei nicht lesbar: {e}") from e
    if not isinstance(db, dict):
        raise IngestError("WowFTDB hat ein unerwartetes Format")
    try:
        parsed = SavedVariablesIn.model_validate(db)
    except ValidationError as e:
        raise IngestError(f"Ungültige Daten: {e.errors()[0]['loc']}: {e.errors()[0]['msg']}") from e
    if parsed.schema_ not in SUPPORTED_SCHEMAS:
        raise IngestError(f"Schema {parsed.schema_} wird nicht unterstützt")
    return parsed


def _insert_events(session: Session, rows: list[dict[str, Any]]) -> list[int]:
    if not rows:
        return []
    for r in rows:
        r.setdefault("key", "")
    stmt = sqlite_insert(Event).values(rows).on_conflict_do_nothing().returning(Event.id)
    return list(session.scalars(stmt))


def _plausible(session: Session, character_id: int, snaps: list[SnapshotIn]) -> list[SnapshotIn]:
    """Wirft Müll-Snapshots weg, die WoW beim Logout/Reload manchmal liefert.

    Dort kommen mitunter ein altes Level und XP-Max 0 zurück. Echte Werte erkennt man daran:
    Unterhalb des Maximallevels ist XP-Max größer 0, und das Level sinkt nie.
    """
    max_level = get_settings().max_level
    top = session.scalar(
        select(func.max(Snapshot.level)).where(
            Snapshot.character_id == character_id, Snapshot.ts < min(s.t for s in snaps)
        )
    )
    keep: list[SnapshotIn] = []
    for s in sorted(snaps, key=lambda s: s.t):
        if (s.xpMax == 0 and s.level < max_level) or s.level < (top or 0):
            continue
        top = max(top or 0, s.level)
        keep.append(s)
    return keep


def store(session: Session, user: User, data: SavedVariablesIn) -> tuple[dict[str, Any], list[int]]:
    """Speichert den Upload. Gibt die Antwort und die IDs neuer Ereignisse zurück."""
    result: dict[str, Any] = {
        "characters": 0,
        "snapshots": 0,
        "events": 0,
        "skipped": [],
        "photoRequests": [],
    }
    new_event_ids: list[int] = []
    ts_now = now()
    for key, c in data.characters.items():
        guid = c.guid or key
        char = session.scalar(select(Character).where(Character.guid == guid))
        if char is None:
            char = Character(user_id=user.id, guid=guid, name=c.name)
            session.add(char)
        elif char.user_id != user.id:
            # Gleicher Charakter von einem anderen Konto (z. B. geteilter PC): nicht übernehmen.
            result["skipped"].append(c.name)
            continue
        char.name = c.name
        char.realm = c.realm
        char.region = c.region
        char.class_ = c.class_
        char.race = c.race
        char.faction = c.faction
        char.last_upload = ts_now
        session.flush()
        result["characters"] += 1

        snaps = _plausible(session, char.id, c.snapshots) if c.snapshots else []
        if snaps:
            rows = [
                {
                    "character_id": char.id,
                    "ts": s.t,
                    "level": s.level,
                    "xp": s.xp,
                    "xp_max": s.xpMax,
                    "rested": s.rested,
                    "played_total": s.playedTotal,
                    "played_level": s.playedLevel,
                    "zone": s.zone,
                    "gold": s.gold,
                }
                for s in snaps
            ]
            stmt = sqlite_insert(Snapshot).values(rows).on_conflict_do_nothing()
            result["snapshots"] += session.execute(stmt).rowcount

        rows = [
            {
                "character_id": char.id,
                "ts": lu.t,
                "type": "level_up",
                "key": str(lu.level),
                "data": {"level": lu.level, "playedTotal": lu.playedTotal},
            }
            for lu in c.levelUps
        ]
        rows += [
            {"character_id": char.id, "ts": d.t, "type": "death", "data": {"level": d.level, "zone": d.zone}}
            for d in c.deathLog
        ]
        rows += [
            {
                "character_id": char.id,
                "ts": b.t,
                "type": "boss",
                "key": str(b.id or b.name)[:100],
                "data": {"name": b.name, "instance": b.instance, "level": b.level},
            }
            for b in c.bossKills
        ]

        # Zustand übernehmen und Änderungen als Ereignisse festhalten.
        new_state = c.state()
        prev = dict(char.state or {})
        ts_state = max((s.t for s in c.snapshots), default=ts_now)
        for type_, ekey, edata in events.derive(prev, new_state):
            rows.append(
                {"character_id": char.id, "ts": ts_state, "type": type_, "key": ekey[:100], "data": edata}
            )
        if new_state or c.photoRequests:
            char.state = {**prev, **new_state, "photoRequests": sorted(set(c.photoRequests))}

        ids = _insert_events(session, rows)
        new_event_ids += ids
        result["events"] += len(ids)

        if c.photoRequests:
            have = set(session.scalars(select(Photo.ts).where(Photo.character_id == char.id)))
            result["photoRequests"] += [
                {"characterId": char.id, "name": char.name, "t": t}
                for t in sorted(set(c.photoRequests))
                if t not in have
            ]

    session.commit()
    return result, new_event_ids
