"""Neue Feed-Ereignisse in Discord-Kanäle posten (pro Gruppe ein Webhook)."""

from __future__ import annotations

import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .events import describe
from .models import Character, Event, Group, GroupMember, now

log = logging.getLogger(__name__)

WEBHOOK_RE = re.compile(
    r"^https://(?:(?:ptb|canary)\.)?(?:discord\.com|discordapp\.com)/api/webhooks/\d+/[\w-]+$"
)
# Ältere Ereignisse (z. B. beim ersten Upload nachgereicht) nicht posten.
MAX_AGE = 12 * 3600
MAX_LINES = 15


def valid_webhook(url: str) -> bool:
    return bool(WEBHOOK_RE.match(url))


def build_posts(session: Session, event_ids: list[int]) -> list[tuple[str, str]]:
    """Gibt (Webhook-URL, Nachricht) je Gruppe zurück."""
    if not event_ids:
        return []
    cutoff = now() - MAX_AGE
    evs = session.scalars(select(Event).where(Event.id.in_(event_ids), Event.ts >= cutoff).order_by(Event.ts))
    lines_by_group: dict[int, list[str]] = {}
    groups: dict[int, Group] = {}
    for e in evs:
        char = session.get(Character, e.character_id)
        if char is None or not char.visible:
            continue
        line = f"**{char.name}** ({char.user.name}) {describe(e.type, e.data)}"
        member_groups = session.scalars(
            select(Group)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.user_id == char.user_id, Group.discord_webhook.is_not(None))
        )
        for g in member_groups:
            groups[g.id] = g
            lines_by_group.setdefault(g.id, []).append(line)
    posts = []
    for gid, lines in lines_by_group.items():
        extra = len(lines) - MAX_LINES
        text = "\n".join(lines[:MAX_LINES])
        if extra > 0:
            text += f"\n… und {extra} weitere"
        posts.append((groups[gid].discord_webhook, text[:1900]))
    return posts


def send(posts: list[tuple[str, str]]) -> None:
    for url, content in posts:
        try:
            r = httpx.post(
                url,
                json={"content": content, "username": "Freundes-Tracker", "allowed_mentions": {"parse": []}},
                timeout=10,
            )
            if r.status_code >= 400:
                log.warning("Discord-Webhook antwortet %s", r.status_code)
        except httpx.HTTPError as e:
            log.warning("Discord-Webhook nicht erreichbar: %s", e)
