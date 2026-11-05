// Klassenfarben (Spielkonvention) und deutsche Bezeichnungen.
export const CLASS_INFO: Record<string, { color: string; name: string }> = {
  WARRIOR: { color: "#C69B6D", name: "Krieger" },
  PALADIN: { color: "#F48CBA", name: "Paladin" },
  HUNTER: { color: "#AAD372", name: "Jäger" },
  ROGUE: { color: "#FFF468", name: "Schurke" },
  PRIEST: { color: "#FFFFFF", name: "Priester" },
  SHAMAN: { color: "#0070DD", name: "Schamane" },
  MAGE: { color: "#3FC7EB", name: "Magier" },
  WARLOCK: { color: "#8788EE", name: "Hexenmeister" },
  DRUID: { color: "#FF7C0A", name: "Druide" },
};

export const RACE_NAMES: Record<string, string> = {
  Human: "Mensch",
  Dwarf: "Zwerg",
  NightElf: "Nachtelf",
  Gnome: "Gnom",
  Orc: "Orc",
  Scourge: "Untoter",
  Undead: "Untoter",
  Tauren: "Tauren",
  Troll: "Troll",
};

export function classColor(token: string | null): string {
  return (token && CLASS_INFO[token]?.color) || "var(--text-2)";
}

export function className(token: string | null): string {
  return (token && CLASS_INFO[token]?.name) || "Unbekannt";
}

export function raceName(token: string | null): string {
  return (token && RACE_NAMES[token]) || token || "";
}
