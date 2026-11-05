export function ago(ts: number | null, now = Date.now() / 1000): string {
  if (!ts) return "nie";
  const s = Math.max(0, Math.floor(now - ts));
  if (s < 60) return "gerade eben";
  if (s < 3600) return `vor ${Math.floor(s / 60)} Min.`;
  if (s < 86400) return `vor ${Math.floor(s / 3600)} Std.`;
  const d = Math.floor(s / 86400);
  return d === 1 ? "vor 1 Tag" : `vor ${d} Tagen`;
}

export function duration(seconds: number | null): string {
  if (seconds == null) return "–";
  const h = Math.floor(seconds / 3600);
  if (h < 1) return `${Math.max(1, Math.round(seconds / 60))} Min.`;
  if (h < 48) return `${h} Std.`;
  const d = Math.floor(h / 24);
  return `${d} T ${h % 24} Std.`;
}

export function number(n: number | null): string {
  return n == null ? "–" : n.toLocaleString("de-DE");
}

export function gold(copper: number | null): string {
  if (copper == null) return "–";
  const g = Math.floor(copper / 10000);
  const s = Math.floor((copper % 10000) / 100);
  return `${g.toLocaleString("de-DE")} G ${s} S`;
}

export function dateTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Älter als dieser Wert gilt ein Upload als veraltet. */
export const STALE_SECONDS = 24 * 3600;
