"""Abgeleitete Kennzahlen: Gesamt-XP, XP pro Stunde, Zeit bis Maximallevel."""

from __future__ import annotations

from collections.abc import Sequence

from .models import Snapshot

# XP von Level L auf L+1 (Classic-Werte). Für Forever prüfen; der Wert für
# das aktuelle Level wird ohnehin aus dem Snapshot (xp_max) übernommen.
XP_TO_NEXT: dict[int, int] = dict(
    enumerate(
        [
            400, 900, 1400, 2100, 2800, 3600, 4500, 5400, 6500, 7600,
            8800, 10100, 11400, 12900, 14400, 16000, 17700, 19400, 21300, 23200,
            25200, 27300, 29400, 31700, 34000, 36400, 38900, 41400, 44300, 47400,
            50800, 54500, 58600, 62800, 67100, 71600, 76100, 80800, 85700, 90700,
            95800, 101000, 106300, 111800, 117500, 123200, 129100, 135100, 141200, 147500,
            153900, 160400, 167100, 173900, 180800, 187900, 195000, 202300, 209800,
        ],
        start=1,
    )
)  # fmt: skip

# Wie viel Spielzeit rückwärts für XP/Stunde betrachtet wird.
RATE_WINDOW = 10 * 3600
RATE_MIN_PLAYED = 20 * 60


def xp_before_level(level: int) -> int:
    return sum(XP_TO_NEXT.get(lv, 0) for lv in range(1, level))


def total_xp(level: int, xp: int) -> int:
    return xp_before_level(level) + xp


def xp_to_max(level: int, xp: int, max_level: int) -> int:
    if level >= max_level:
        return 0
    return max(0, xp_before_level(max_level) - total_xp(level, xp))


def xp_per_hour(snaps: Sequence[Snapshot]) -> float | None:
    """XP pro Stunde Spielzeit, aus Snapshots (aufsteigend nach Zeit)."""
    with_played = [s for s in snaps if s.played_total is not None]
    if len(with_played) < 2:
        return None
    last = with_played[-1]
    first = last
    for s in reversed(with_played[:-1]):
        if last.played_total - s.played_total > RATE_WINDOW:
            break
        first = s
    played = last.played_total - first.played_total
    if played < RATE_MIN_PLAYED:
        return None
    gained = total_xp(last.level, last.xp) - total_xp(first.level, first.xp)
    if gained <= 0:
        return None
    return gained / played * 3600


def eta_seconds(level: int, xp: int, rate: float | None, max_level: int) -> int | None:
    if level >= max_level:
        return 0
    if not rate:
        return None
    return int(xp_to_max(level, xp, max_level) / rate * 3600)
