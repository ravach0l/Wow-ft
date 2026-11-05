// Freigaben je Charakter. Die Schlüssel müssen zu server/wowft/privacy.py (CATEGORIES) passen.
// Level und XP sind immer sichtbar.
export const SHARE_CATEGORIES: { key: string; label: string; hint?: string }[] = [
  {
    key: "pace",
    label: "Spielzeit und Tempo",
    hint: "XP pro Stunde und Zeit bis zum Maximallevel hängen an der Spielzeit. Andere sehen sie nur, wenn der Rennen-Modus an ist.",
  },
  { key: "gold", label: "Gold" },
  { key: "zone", label: "Aufenthaltsort" },
  { key: "gear", label: "Ausrüstung" },
  { key: "skills", label: "Berufe" },
  { key: "reputation", label: "Ruf" },
  { key: "talents", label: "Talente" },
  { key: "materials", label: "Handwerksmaterialien" },
  { key: "deaths", label: "Tode" },
  { key: "bosses", label: "Boss-Kills" },
  { key: "photo", label: "Foto" },
];

const LABELS = new Map(SHARE_CATEGORIES.map((c) => [c.key, c.label]));

/** Namen der ausgeblendeten Kategorien für einen Hinweis. `raceOn`: Spielzeit gilt nur dann als „ausgeblendet“. */
export function hiddenLabels(hidden: string[] | undefined, raceOn: boolean): string[] {
  return (hidden ?? []).filter((k) => k !== "pace" || raceOn).map((k) => LABELS.get(k) ?? k);
}
