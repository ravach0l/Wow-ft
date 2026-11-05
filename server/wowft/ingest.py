"""Nimmt SavedVariables entgegen und schreibt neue Snapshots/Ereignisse.

Doppelte Uploads sind harmlos: Snapshots sind über (Charakter, Zeitpunkt)
eindeutig, Ereignisse über (Charakter, Zeitpunkt, Typ).
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from . import svparse
from .models import Character, Event, Snapshot, User, now

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

    _lists = field_validator("snapshots", "levelUps", mode="before")(_empty_dict_to_list)


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


def store(session: Session, user: User, data: SavedVariablesIn) -> dict[str, Any]:
    result: dict[str, Any] = {"characters": 0, "snapshots": 0, "events": 0, "skipped": []}
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

        if c.snapshots:
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
                for s in c.snapshots
            ]
            stmt = sqlite_insert(Snapshot).values(rows).on_conflict_do_nothing()
            result["snapshots"] += session.execute(stmt).rowcount

        if c.levelUps:
            rows = [
                {
                    "character_id": char.id,
                    "ts": lu.t,
                    "type": "level_up",
                    "data": {"level": lu.level, "playedTotal": lu.playedTotal},
                }
                for lu in c.levelUps
            ]
            stmt = sqlite_insert(Event).values(rows).on_conflict_do_nothing()
            result["events"] += session.execute(stmt).rowcount

    session.commit()
    return result
