import type { CharacterState } from "./types";

export type SortMode = "level" | "rate" | "played";

export const SORT_LABELS: Record<SortMode, string> = {
  level: "Level",
  rate: "XP/Std.",
  played: "Spielzeit",
};

export function compare(mode: SortMode) {
  return (a: CharacterState, b: CharacterState): number => {
    switch (mode) {
      case "rate":
        return (b.xpPerHour ?? -1) - (a.xpPerHour ?? -1) || b.totalXp - a.totalXp;
      case "played":
        return (b.playedTotal ?? -1) - (a.playedTotal ?? -1) || b.totalXp - a.totalXp;
      default:
        return b.totalXp - a.totalXp || a.name.localeCompare(b.name);
    }
  };
}

export interface PersonGroup {
  ownerId: number;
  ownerName: string;
  main: CharacterState;
  twinks: CharacterState[];
}

/** Gruppiert nach Person; der weiteste Charakter ist der Hauptcharakter. */
export function groupByOwner(chars: CharacterState[], mode: SortMode): PersonGroup[] {
  const byOwner = new Map<number, CharacterState[]>();
  for (const c of chars) {
    const list = byOwner.get(c.ownerId) ?? [];
    list.push(c);
    byOwner.set(c.ownerId, list);
  }
  const groups: PersonGroup[] = [];
  for (const [ownerId, list] of byOwner) {
    list.sort(compare("level"));
    const [main, ...twinks] = list;
    groups.push({ ownerId, ownerName: main.ownerName, main, twinks: twinks.sort(compare(mode)) });
  }
  const cmp = compare(mode);
  return groups.sort((a, b) => cmp(a.main, b.main));
}
