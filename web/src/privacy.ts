// Freigaben je Charakter. Die Schlüssel müssen zu server/wowft/privacy.py (CATEGORIES) passen.
// Level und XP sind immer sichtbar.
export const SHARE_CATEGORIES: { key: string; label: string; hint?: string }[] = [
  {
    key: "pace",
    label: "Spielzeit",
    hint: "Andere sehen sie nur, wenn der Rennen-Modus an ist.",
  },
  {
    key: "rate",
    label: "Tempo (XP pro Stunde)",
    hint: "Auch die Zeit bis zum Maximallevel. Standardmäßig aus: Aus Tempo und Level lässt sich die Spielzeit ungefähr errechnen.",
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
