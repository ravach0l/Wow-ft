import type { CharacterState } from "./types";

export interface ZoneGroup {
  zone: string;
  chars: CharacterState[];
  /** verschiedene Personen in dieser Zone */
  people: number;
}

/**
 * „Wer ist wo“: Charaktere nach ihrer letzten bekannten Zone gruppiert. Ohne Zeitangabe,
 * damit niemand ablesen kann, wann jemand spielt. Charaktere mit ausgeblendetem
 * Aufenthaltsort (zone = null) fehlen. Zonen mit mehr Personen zuerst.
 */
export function groupByZone(chars: CharacterState[]): ZoneGroup[] {
  const map = new Map<string, CharacterState[]>();
  for (const c of chars) {
    if (!c.zone) continue;
    const list = map.get(c.zone) ?? [];
    list.push(c);
    map.set(c.zone, list);
  }
  return [...map.entries()]
    .map(([zone, list]) => ({
      zone,
      chars: list.sort((a, b) => b.level - a.level || a.name.localeCompare(b.name)),
      people: new Set(list.map((c) => c.ownerId)).size,
    }))
    .sort((a, b) => b.people - a.people || b.chars.length - a.chars.length || a.zone.localeCompare(b.zone));
}
