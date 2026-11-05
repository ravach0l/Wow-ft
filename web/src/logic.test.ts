import { describe, expect, it } from "vitest";
import { ago, duration, gold } from "./format";
import { groupByOwner } from "./sort";
import type { CharacterState } from "./types";

function char(p: Partial<CharacterState>): CharacterState {
  return {
    id: 1, name: "A", class: "MAGE", race: "Human", faction: "Alliance", region: "EU",
    ownerId: 1, ownerName: "x", ts: 0, lastUpload: 0, level: 1, xp: 0, xpMax: 400, rested: 0,
    zone: null, playedTotal: null, playedLevel: null, gold: null, totalXp: 0, xpPerHour: null,
    etaSeconds: null, behindLeader: 0, ...p,
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
