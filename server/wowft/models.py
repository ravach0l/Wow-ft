"""Datenmodell. Zeitpunkte sind Unix-Sekunden (UTC) als Integer."""

import time
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now() -> int:
    return int(time.time())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    auth_sub: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))
    created: Mapped[int] = mapped_column(Integer, default=now)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    invite_code: Mapped[str] = mapped_column(String(64), unique=True)
    discord_webhook: Mapped[str | None] = mapped_column(String(300))
    created: Mapped[int] = mapped_column(Integer, default=now)

    members: Mapped[list["GroupMember"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class GroupMember(Base):
    __tablename__ = "group_members"

    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="member")  # owner | member
    joined: Mapped[int] = mapped_column(Integer, default=now)

    group: Mapped[Group] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefix: Mapped[str] = mapped_column(String(16))
    created: Mapped[int] = mapped_column(Integer, default=now)
    last_used: Mapped[int | None] = mapped_column(Integer)
    revoked: Mapped[int | None] = mapped_column(Integer)


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Forever hat keine wählbaren Realms; die GUID identifiziert den Charakter eindeutig.
    guid: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    realm: Mapped[str | None] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(8))
    class_: Mapped[str | None] = mapped_column("class", String(32))
    race: Mapped[str | None] = mapped_column(String(32))
    faction: Mapped[str | None] = mapped_column(String(16))
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    gold_visible: Mapped[bool] = mapped_column(Boolean, default=False)
    # Freigaben je Kategorie (siehe privacy.py); fehlende Schlüssel gelten als Standardwert.
    share: Mapped[dict[str, bool] | None] = mapped_column(JSON)
    created: Mapped[int] = mapped_column(Integer, default=now)
    last_upload: Mapped[int | None] = mapped_column(Integer)
    # Jüngster Stand aus dem Addon: Berufe, Ausrüstung, Ruf, Talente, Material, Tode.
    state: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    user: Mapped[User] = relationship()


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (UniqueConstraint("character_id", "ts"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"))
    ts: Mapped[int] = mapped_column(Integer)
    level: Mapped[int] = mapped_column(Integer)
    xp: Mapped[int] = mapped_column(Integer)
    xp_max: Mapped[int] = mapped_column(Integer)
    rested: Mapped[int] = mapped_column(Integer, default=0)
    played_total: Mapped[int | None] = mapped_column(Integer)
    played_level: Mapped[int | None] = mapped_column(Integer)
    zone: Mapped[str | None] = mapped_column(String(100))
    gold: Mapped[int | None] = mapped_column(Integer)
    extras: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("character_id", "ts", "type", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"))
    ts: Mapped[int] = mapped_column(Integer, index=True)
    type: Mapped[str] = mapped_column(String(32))
    # Unterscheidet mehrere Ereignisse gleichen Typs zur selben Zeit (z. B. Beruf, Slot).
    key: Mapped[str] = mapped_column(String(100), default="")
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (UniqueConstraint("character_id", "ts"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    ts: Mapped[int] = mapped_column(Integer)
    level: Mapped[int | None] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(String(255))
    created: Mapped[int] = mapped_column(Integer, default=now)


class AppSetting(Base):
    """Einstellungen für die ganze Seite, z. B. welche Module aktiv sind."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)


class Pairing(Base):
    """Laufende Kopplung eines Uploaders (kurzlebig, wird nach Gebrauch gelöscht).

    kind = "device": Der Uploader hat sie gestartet und zeigt `user_code`; ein angemeldeter
    Nutzer bestätigt im Browser, der Uploader holt danach mit seinem geheimen Schlüssel
    (`device_hash`) einen neuen Upload-Token ab.
    kind = "game": Ein angemeldeter Nutzer hat im Profil einen Code fürs Spiel erzeugt; der
    Uploader findet ihn in WowFT.lua und tauscht ihn gegen einen Upload-Token.
    Es wird nie ein Token gespeichert: Er entsteht erst beim Abholen.
    """

    __tablename__ = "pairings"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    user_code: Mapped[str] = mapped_column(String(16), unique=True)
    device_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    device_name: Mapped[str | None] = mapped_column(String(100))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created: Mapped[int] = mapped_column(Integer, default=now)
    expires: Mapped[int] = mapped_column(Integer, index=True)


class SpellIcon(Base):
    """Icon-Name je Zauber-ID (Cache für Wowhead-Abfragen). icon = None: nichts gefunden."""

    __tablename__ = "spell_icons"

    spell_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    icon: Mapped[str | None] = mapped_column(String(100))
    checked: Mapped[int] = mapped_column(Integer, default=now)


class MaterialRequest(Base):
    """Material-Wunsch in einer Gruppe („Ich suche 10 Kupferbarren“), läuft nach 7 Tagen ab."""

    __tablename__ = "material_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    item_id: Mapped[int | None] = mapped_column(Integer)
    item_name: Mapped[str] = mapped_column(String(150))
    count: Mapped[int] = mapped_column(Integer)
    created: Mapped[int] = mapped_column(Integer, default=now)
    expires: Mapped[int] = mapped_column(Integer)
    done: Mapped[int | None] = mapped_column(Integer)

    user: Mapped[User] = relationship()
