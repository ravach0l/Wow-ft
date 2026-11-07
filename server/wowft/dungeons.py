"""Dungeons und Schlachtzüge mit empfohlenen Stufen (Classic-Werte, für Forever prüfen).

`names` enthält die Instanznamen, die `GetInstanceInfo()` im Spiel liefern kann (deutsch und
englisch). Darüber werden besiegte Bosse (Ereignis `boss`, Feld `instance`) einem Dungeon
zugeordnet. Flügel derselben Instanz (Scharlachrotes Kloster, Düsterbruch, Schwarzfelsspitze)
teilen sich den Namen; ein Boss dort zählt für alle Flügel als „schon drin gewesen“.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Dungeon:
    key: str
    name: str  # Anzeige (deutsch)
    zone: str
    min: int
    max: int
    raid: bool = False
    size: int = 5
    names: tuple[str, ...] = field(default_factory=tuple)

    def out(self) -> dict:
        d = asdict(self)
        d.pop("names")
        return d


def D(key, name, zone, lo, hi, *names, raid=False, size=5):  # noqa: N802
    return Dungeon(key, name, zone, lo, hi, raid, size, (name, *names))


DUNGEONS: tuple[Dungeon, ...] = (
    D("rfc", "Der Flammenschlund", "Orgrimmar", 13, 18, "Ragefire Chasm"),
    D("wc", "Die Höhlen des Wehklagens", "Brachland", 17, 24, "Wailing Caverns"),
    D("dm", "Die Todesminen", "Westfall", 17, 26, "The Deadmines", "Deadmines"),
    D("sfk", "Burg Schattenfang", "Silberwald", 22, 30, "Shadowfang Keep"),
    D("bfd", "Tiefschwarze Grotte", "Eschental", 24, 32, "Blackfathom Deeps"),
    D("stocks", "Das Verlies", "Sturmwind", 24, 32, "The Stockade", "Stormwind Stockade"),
    D("gnomer", "Gnomeregan", "Dun Morogh", 29, 38),
    D("rfk", "Kral der Klingenhauer", "Brachland", 29, 38, "Razorfen Kraul"),
    D(
        "sm_gy",
        "Scharlachrotes Kloster: Friedhof",
        "Tirisfal",
        26,
        36,
        *(_sm := ("Das Scharlachrote Kloster", "Scharlachrotes Kloster", "Scarlet Monastery")),
    ),
    D("sm_lib", "Scharlachrotes Kloster: Bibliothek", "Tirisfal", 29, 39, *_sm),
    D("sm_arm", "Scharlachrotes Kloster: Waffenkammer", "Tirisfal", 32, 42, *_sm),
    D("sm_cath", "Scharlachrotes Kloster: Kathedrale", "Tirisfal", 35, 45, *_sm),
    D("rfd", "Hügel der Klingenhauer", "Brachland", 37, 46, "Razorfen Downs"),
    D("ulda", "Uldaman", "Ödland", 41, 51),
    D("zf", "Zul'Farrak", "Tanaris", 44, 54),
    D("mara", "Maraudon", "Desolace", 46, 55),
    D(
        "st",
        "Der Tempel von Atal'Hakkar",
        "Sümpfe des Elends",
        50,
        56,
        "Versunkener Tempel",
        "Sunken Temple",
        "The Temple of Atal'Hakkar",
    ),
    D("brd", "Schwarzfelstiefen", "Schwarzfels", 52, 60, "Blackrock Depths"),
    D(
        "lbrs",
        "Untere Schwarzfelsspitze",
        "Schwarzfels",
        55,
        60,
        *(_brs := ("Schwarzfelsspitze", "Blackrock Spire")),
    ),
    D("dm_east", "Düsterbruch: Ost", "Feralas", 55, 60, *(_dim := ("Düsterbruch", "Dire Maul"))),
    D("dm_west", "Düsterbruch: West", "Feralas", 57, 60, *_dim),
    D("dm_north", "Düsterbruch: Nord", "Feralas", 57, 60, *_dim),
    D("scholo", "Scholomance", "Westliche Pestländer", 58, 60),
    D("strat", "Stratholme", "Östliche Pestländer", 58, 60),
    D("ubrs", "Obere Schwarzfelsspitze", "Schwarzfels", 58, 60, *_brs, raid=True, size=10),
    D("zg", "Zul'Gurub", "Schlingendorntal", 60, 60, raid=True, size=20),
    D("aq20", "Ruinen von Ahn'Qiraj", "Silithus", 60, 60, "Ruins of Ahn'Qiraj", raid=True, size=20),
    D("mc", "Geschmolzener Kern", "Schwarzfels", 60, 60, "Molten Core", raid=True, size=40),
    D("ony", "Onyxias Hort", "Düstermarschen", 60, 60, "Onyxia's Lair", raid=True, size=40),
    D("bwl", "Pechschwingenhort", "Schwarzfels", 60, 60, "Blackwing Lair", raid=True, size=40),
    D("aq40", "Tempel von Ahn'Qiraj", "Silithus", 60, 60, "Temple of Ahn'Qiraj", raid=True, size=40),
    D("naxx", "Naxxramas", "Östliche Pestländer", 60, 60, raid=True, size=40),
)


def _norm(name: str) -> str:
    return re.sub(r"[^a-zäöüß]", "", (name or "").lower())


_BY_NAME: dict[str, list[str]] = {}
for _d in DUNGEONS:
    for _n in _d.names:
        _BY_NAME.setdefault(_norm(_n), []).append(_d.key)


def keys_for_instance(instance: str | None) -> list[str]:
    """Dungeon-Schlüssel zu einem Instanznamen aus dem Spiel ([] = unbekannt)."""
    return list(_BY_NAME.get(_norm(instance or ""), []))
