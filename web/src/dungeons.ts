import type { Dungeon, PlannerCharacter } from "./types";

/** fit = Level im empfohlenen Bereich, soon = bis 3 Level darunter, over = darüber. */
export type Fit = "fit" | "soon" | "over";

export const SOON_LEVELS = 3;

export function fitFor(level: number, d: Dungeon): Fit | null {
  if (level > d.max) return "over";
  if (level >= d.min) return "fit";
  if (level >= d.min - SOON_LEVELS) return "soon";
  return null;
}

export interface FactionPlan {
  faction: string; // "Alliance" | "Horde" | "?"
  fit: PlannerCharacter[];
  soon: PlannerCharacter[];
  over: PlannerCharacter[];
  /** Personen (nicht Charaktere), die mit mindestens einem Charakter passen. */
  people: number;
}

export interface DungeonPlan {
  dungeon: Dungeon;
  factions: FactionPlan[];
  /** größte Personenzahl einer Fraktion */
  best: number;
}

const byLevel = (a: PlannerCharacter, b: PlannerCharacter) => b.level - a.level || a.name.localeCompare(b.name);

/**
 * Wer passt in welchen Dungeon? Getrennt nach Fraktion, weil Allianz und Horde nicht
 * zusammen spielen können. Ohne `showAll` nur Dungeons, in die jemand passt oder bald passt.
 */
export function planDungeons(dungeons: Dungeon[], chars: PlannerCharacter[], showAll = false): DungeonPlan[] {
  const sorted = [...dungeons].sort((a, b) => Number(a.raid) - Number(b.raid) || a.min - b.min || a.max - b.max);
  const plans: DungeonPlan[] = [];
  for (const d of sorted) {
    const byFaction = new Map<string, FactionPlan>();
    for (const c of chars) {
      const f = fitFor(c.level, d);
      if (!f) continue;
      const key = c.faction ?? "?";
      const plan = byFaction.get(key) ?? { faction: key, fit: [], soon: [], over: [], people: 0 };
      plan[f].push(c);
      byFaction.set(key, plan);
    }
    const factions = [...byFaction.values()]
      .map((p) => ({
        ...p,
        fit: p.fit.sort(byLevel),
        soon: p.soon.sort(byLevel),
        over: p.over.sort(byLevel),
        people: new Set(p.fit.map((c) => c.ownerId)).size,
      }))
      .filter((p) => showAll || p.fit.length > 0 || p.soon.length > 0)
      .sort((a, b) => b.people - a.people || a.faction.localeCompare(b.faction));
    if (!showAll && factions.length === 0) continue;
    plans.push({ dungeon: d, factions, best: Math.max(0, ...factions.map((f) => f.people)) });
  }
  return plans;
}

/** Vorschläge für „heute“: Dungeons (keine Schlachtzüge), in die mindestens zwei Personen passen. */
export function suggestions(plans: DungeonPlan[], limit = 3): DungeonPlan[] {
  return plans
    .filter((p) => !p.dungeon.raid && p.best >= 2)
    .sort((a, b) => b.best - a.best || a.dungeon.min - b.dungeon.min)
    .slice(0, limit);
}

export const FACTION_NAMES: Record<string, string> = { Alliance: "Allianz", Horde: "Horde", "?": "Fraktion unbekannt" };
