import type { Talent } from "./types";

export interface TreeCell {
  talent: Talent;
  row: number; // 0 = oberste Reihe
  col: number; // 0 = linke Spalte
}

export interface TreeGrid {
  rows: number;
  cols: number;
  cells: TreeCell[];
}

/**
 * Legt die Talente eines Baums auf ein Raster. Zeile und Spalte ergeben sich aus der Reihenfolge der
 * vorkommenden `tier`- und `col`-Werte (nicht aus deren Betrag), damit es für Klassik-Reihen (1..7)
 * wie für Koordinaten des modernen Talentsystems gleich funktioniert. Talente ohne Position
 * (ältere Uploads) stehen gesammelt in einer letzten Reihe.
 */
export function talentGrid(talents: Talent[]): TreeGrid {
  const rowKeys = [...new Set(talents.map((t) => t.tier).filter((v): v is number => v != null))].sort((a, b) => a - b);
  const colKeys = [...new Set(talents.map((t) => t.col).filter((v): v is number => v != null))].sort((a, b) => a - b);
  const loose = talents.filter((t) => t.tier == null || t.col == null);
  const cells: TreeCell[] = [];
  for (const t of talents) {
    if (t.tier == null || t.col == null) continue;
    cells.push({ talent: t, row: rowKeys.indexOf(t.tier), col: colKeys.indexOf(t.col) });
  }
  const cols = Math.max(colKeys.length, loose.length > 0 ? Math.min(loose.length, 6) : 0);
  loose.forEach((t, i) => cells.push({ talent: t, row: rowKeys.length + Math.floor(i / Math.max(cols, 1)), col: i % Math.max(cols, 1) }));
  const rows = cells.reduce((m, c) => Math.max(m, c.row + 1), 0);
  return { rows, cols, cells };
}
