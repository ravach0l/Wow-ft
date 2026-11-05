import { hiddenLabels, SHARE_CATEGORIES } from "./privacy";
import { describe, expect, it } from "vitest";
import { ago, duration, gold } from "./format";
import { mergeMaterials } from "./pages/CharacterPage";
import { talentGrid } from "./talents";
import { toSeries } from "./pages/RacePage";
import { groupByOwner } from "./sort";
import type { CharacterState } from "./types";

function char(p: Partial<CharacterState>): CharacterState {
  return {
    id: 1, name: "A", class: "MAGE", race: "Human", faction: "Alliance", region: "EU",
    ownerId: 1, ownerName: "x", ts: 0, lastUpload: 0, level: 1, xp: 0, xpMax: 400, rested: 0,
    zone: null, playedTotal: null, playedLevel: null, gold: null, totalXp: 0, xpPerHour: null,
    etaSeconds: null, behindLeader: 0, deaths: null, photoUrl: null, hidden: [], ...p,
  };
}

describe("format", () => {
  it("ago", () => {
    expect(ago(1000, 1030)).toBe("gerade eben");
    expect(ago(1000, 1000 + 125)).toBe("vor 2 Min.");
    expect(ago(1000, 1000 + 7300)).toBe("vor 2 Std.");
    expect(ago(1000, 1000 + 86400)).toBe("vor 1 Tag");
    expect(ago(null)).toBe("nie");
  });
  it("duration", () => {
    expect(duration(null)).toBe("–");
    expect(duration(600)).toBe("10 Min.");
    expect(duration(5 * 3600)).toBe("5 Std.");
    expect(duration(50 * 3600)).toBe("2 T 2 Std.");
  });
  it("gold", () => {
    expect(gold(1234567)).toBe("123 G 45 S");
  });
});

describe("groupByOwner", () => {
  const chars = [
    char({ id: 1, ownerId: 1, ownerName: "anna", name: "Main", totalXp: 500, xpPerHour: 100 }),
    char({ id: 2, ownerId: 1, ownerName: "anna", name: "Twink", totalXp: 50, xpPerHour: 9000 }),
    char({ id: 3, ownerId: 2, ownerName: "ben", name: "Ben", totalXp: 300, xpPerHour: 5000 }),
  ];
  it("highest character is main, people sorted by level", () => {
    const g = groupByOwner(chars, "level");
    expect(g.map((p) => p.main.name)).toEqual(["Main", "Ben"]);
    expect(g[0].twinks.map((c) => c.name)).toEqual(["Twink"]);
  });
  it("rate sorts people by their main", () => {
    expect(groupByOwner(chars, "rate").map((p) => p.ownerName)).toEqual(["ben", "anna"]);
  });
});

describe("phase 4 helpers", () => {
  it("toSeries switches axis and drops points without playtime", () => {
    const race = [{ id: 1, name: "A", class: "MAGE", ownerName: "x", points: [[100, null, 5], [200, 3600, 6.5]] as [number, number | null, number][] }];
    expect(toSeries(race, "calendar")[0].points).toEqual([{ x: 100, y: 5 }, { x: 200, y: 6.5 }]);
    expect(toSeries(race, "played")[0].points).toEqual([{ x: 3600, y: 6.5 }]);
  });
  it("mergeMaterials adds bags and bank", () => {
    const m = mergeMaterials([{ id: 1, name: "Erz", count: 3 }], [{ id: 1, name: "Erz", count: 4 }, { id: 2, name: "Stoff", count: 1 }]);
    expect(m).toEqual([
      { id: 1, name: "Erz", bags: 3, bank: 4 },
      { id: 2, name: "Stoff", bags: 0, bank: 1 },
    ]);
  });
});


describe("Freigaben", () => {
  it("nennt ausgeblendete Kategorien; Spielzeit nur bei eingeschaltetem Rennen-Modus", () => {
    expect(hiddenLabels(["gold", "gear"], false)).toEqual(["Gold", "Ausrüstung"]);
    expect(hiddenLabels(["pace", "gold"], false)).toEqual(["Gold"]);
    expect(hiddenLabels(["pace"], true)).toEqual(["Spielzeit"]);
    expect(hiddenLabels(["rate"], false)).toEqual(["Tempo (XP pro Stunde)"]);
    expect(hiddenLabels(undefined, true)).toEqual([]);
  });

  it("deckt alle Server-Kategorien ab (server/wowft/privacy.py)", () => {
    const server = ["pace", "rate", "gold", "zone", "gear", "skills", "reputation", "talents", "materials", "deaths", "bosses", "photo"];
    expect(SHARE_CATEGORIES.map((c) => c.key).sort()).toEqual([...server].sort());
  });
});

describe("talentGrid", () => {
  it("legt Talente nach Reihe und Spalte ab, unabhängig vom Koordinatensystem", () => {
    const g = talentGrid([
      { name: "A", rank: 1, max: 1, tier: 2400, col: 900 },
      { name: "B", rank: 0, max: 3, tier: 1200, col: 1500 },
      { name: "C", rank: 2, max: 2, tier: 1200, col: 900 },
    ]);
    expect([g.rows, g.cols]).toEqual([2, 2]);
    const at = (n: string) => g.cells.find((c) => c.talent.name === n)!;
    expect([at("C").row, at("C").col]).toEqual([0, 0]);
    expect([at("B").row, at("B").col]).toEqual([0, 1]);
    expect([at("A").row, at("A").col]).toEqual([1, 0]);
  });

  it("sammelt Talente ohne Position in einer Reihe darunter", () => {
    const g = talentGrid([
      { name: "A", rank: 1, max: 1, tier: 1, col: 1 },
      { name: "alt", rank: 2, max: 2 },
    ]);
    expect(g.cells.find((c) => c.talent.name === "alt")!.row).toBe(1);
    expect(g.rows).toBe(2);
  });
});
