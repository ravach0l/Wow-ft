import type { History } from "../types";

type Axis = "calendar" | "played";

/** Level (mit Anteil des Levels) über Kalender- oder Spielzeit. */
export default function LevelChart({ snapshots, axis }: { snapshots: History["snapshots"]; axis: Axis }) {
  const pts = snapshots
    .map((s) => ({
      x: axis === "calendar" ? s.ts : s.playedTotal,
      y: s.level + (s.xpMax > 0 ? s.xp / s.xpMax : 0),
    }))
    .filter((p): p is { x: number; y: number } => p.x != null);

  if (pts.length < 2) return <p className="muted">Für ein Diagramm braucht es mindestens zwei Messpunkte.</p>;

  const W = 640, H = 220, L = 34, R = 10, T = 10, B = 26;
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.floor(Math.min(...ys)), y1 = Math.ceil(Math.max(...ys)) || y0 + 1;
  const sx = (x: number) => L + ((x - x0) / (x1 - x0 || 1)) * (W - L - R);
  const sy = (y: number) => H - B - ((y - y0) / (y1 - y0 || 1)) * (H - T - B);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join("");
  const step = Math.max(1, Math.ceil((y1 - y0) / 5));
  const ticks: number[] = [];
  for (let y = y0; y <= y1; y += step) ticks.push(y);
  const label = (x: number) =>
    axis === "calendar"
      ? new Date(x * 1000).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })
      : `${Math.round(x / 3600)} Std.`;

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Level-Verlauf">
      {ticks.map((y) => (
        <g key={y}>
          <line x1={L} x2={W - R} y1={sy(y)} y2={sy(y)} stroke="var(--line)" />
          <text x={L - 6} y={sy(y) + 4} textAnchor="end">{y}</text>
        </g>
      ))}
      <text x={L} y={H - 6}>{label(x0)}</text>
      <text x={W - R} y={H - 6} textAnchor="end">{label(x1)}</text>
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2.5} strokeLinejoin="round" />
    </svg>
  );
}
