"""Wochenrückblick in Discord: sonntags ab 19 Uhr (Europe/Berlin), einmal pro Woche und Gruppe.

Inhalt: Level-Sprünge, besiegte Bosse, Tode und Berufsstufen der Woche. Keine Spielzeit und
keine Uhrzeiten. Ausgeblendetes (Freigaben) bleibt draußen; maßgeblich ist die Sicht eines
Fremden, weil der Discord-Kanal nicht nur aus Gruppenmitgliedern bestehen muss.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import discord, privacy
from .db import new_session
from .models import AppSetting, Character, Event, Group, GroupMember, Snapshot

log = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Berlin")
SEND_WEEKDAY = 6  # Sonntag
SEND_HOUR = 19


def week_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Montag 00:00 bis jetzt (lokale Zeit)."""
    local = now.astimezone(TZ)
    start = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, local


def week_key(now: datetime) -> str:
    y, w, _ = now.astimezone(TZ).isocalendar()
    return f"{y}-W{w:02d}"


def _characters(session: Session, group_id: int) -> list[Character]:
    member_ids = select(GroupMember.user_id).where(GroupMember.group_id == group_id)
    return list(
        session.scalars(
            select(Character).where(Character.user_id.in_(member_ids), Character.visible.is_(True))
        )
    )


def build_report(session: Session, group: Group, now: datetime) -> str | None:
    """Text des Wochenrückblicks; None, wenn in der Woche nichts passiert ist."""
    start, end = week_bounds(now)
    t0, t1 = int(start.timestamp()), int(end.timestamp())
    levels: list[tuple[int, str]] = []
    bosses: dict[str, list[str]] = defaultdict(list)
    deaths: Counter[str] = Counter()
    skills: list[str] = []
    for c in _characters(session, group.id):
        label = f"{c.name} ({c.user.name})"
        before = session.scalar(
            select(Snapshot.level)
            .where(Snapshot.character_id == c.id, Snapshot.ts < t0)
            .order_by(Snapshot.ts.desc())
        )
        week = list(
            session.scalars(
                select(Snapshot.level)
                .where(Snapshot.character_id == c.id, Snapshot.ts >= t0, Snapshot.ts <= t1)
                .order_by(Snapshot.ts)
            )
        )
        if week:
            first = before if before is not None else week[0]
            if week[-1] > first:
                levels.append((week[-1] - first, f"• {label}: {first} → {week[-1]}"))
        events = session.scalars(
            select(Event).where(Event.character_id == c.id, Event.ts >= t0, Event.ts <= t1).order_by(Event.ts)
        )
        for e in events:
            if not privacy.event_visible(c, None, e.type):
                continue
            d = e.data or {}
            if e.type == "boss" and d.get("name"):
                if c.name not in bosses[d["name"]]:
                    bosses[d["name"]].append(c.name)
            elif e.type == "death":
                deaths[c.name] += 1
            elif e.type == "skill":
                skills.append(f"{c.name}: {d.get('name')} {d.get('rank')}")

    if not (levels or bosses or deaths or skills):
        return None
    lines = [f"**Wochenrückblick {group.name}** ({start:%d.%m.} – {end:%d.%m.})"]
    if levels:
        lines.append("")
        lines.append("**Level**")
        lines += [line for _, line in sorted(levels, key=lambda x: -x[0])]
    if bosses:
        lines.append("")
        lines.append("**Bosse**: " + " · ".join(f"{b} ({', '.join(who)})" for b, who in bosses.items()))
    if deaths:
        total = sum(deaths.values())
        most, n = deaths.most_common(1)[0]
        extra = f", am häufigsten {most} ({n})" if len(deaths) > 1 else ""
        lines.append(f"**Tode**: {total}{extra}")
    if skills:
        lines.append("**Berufe**: " + " · ".join(skills[:10]))
    return "\n".join(lines)[:1900]


def run_once(now: datetime | None = None) -> int:
    """Schickt fällige Wochenrückblicke. Gibt die Zahl der gesendeten zurück."""
    now = now or datetime.now(TZ)
    local = now.astimezone(TZ)
    if local.weekday() != SEND_WEEKDAY or local.hour < SEND_HOUR:
        return 0
    key = week_key(now)
    sent = 0
    with new_session() as session:
        groups = session.scalars(
            select(Group).where(Group.discord_webhook.is_not(None), Group.weekly_report.is_(True))
        )
        for g in groups:
            setting_key = f"weekly:{g.id}"
            row = session.get(AppSetting, setting_key)
            if row is not None and row.value == key:
                continue
            text = build_report(session, g, now)
            if text:
                discord.send([(g.discord_webhook, text)])
                sent += 1
            if row is None:
                session.add(AppSetting(key=setting_key, value=key))
            else:
                row.value = key
            session.commit()
    return sent


async def loop() -> None:
    """Hintergrundschleife im Server: alle 10 Minuten prüfen."""
    import asyncio

    from starlette.concurrency import run_in_threadpool

    while True:
        try:
            await run_in_threadpool(run_once)
        except Exception:  # noqa: BLE001 – der Server soll weiterlaufen
            log.exception("Wochenrückblick fehlgeschlagen")
        await asyncio.sleep(600)
