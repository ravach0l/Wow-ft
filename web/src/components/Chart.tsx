export interface Series {
  name: string;
  color: string;
  points: { x: number; y: number }[];
}

export type Axis = "calendar" | "played";

/** Liniendiagramm Level über Zeit; eine Linie pro Serie. */
export default function Chart({ series, axis, height = 240 }: { series: Series[]; axis: Axis; height?: number }) {
  const usable = series.filter((s) => s.points.length > 0);
  const all = usable.flatMap((s) => s.points);
  if (all.length < 2) return <p className="muted">Für ein Diagramm braucht es mindestens zwei Messpunkte.</p>;

  const W = 640, H = height, L = 34, R = 12, T = 10, B = 26;
  const xs = all.map((p) => p.x), ys = all.map((p) => p.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.floor(Math.min(...ys));
  const y1 = Math.max(y0 + 1, Math.ceil(Math.max(...ys)));
  const sx = (x: number) => L + ((x - x0) / (x1 - x0 || 1)) * (W - L - R);
  const sy = (y: number) => H - B - ((y - y0) / (y1 - y0)) * (H - T - B);
  const step = Math.max(1, Math.ceil((y1 - y0) / 5));
  const ticks: number[] = [];
  for (let y = y0; y <= y1; y += step) ticks.push(y);
  const label = (x: number) =>
    axis === "calendar"
      ? new Date(x * 1000).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })
      : `${Math.round(x / 3600)} Std.`;

  return (
    <>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Level-Verlauf">
        {ticks.map((y) => (
          <g key={y}>
            <line x1={L} x2={W - R} y1={sy(y)} y2={sy(y)} stroke="var(--line)" />
            <text x={L - 6} y={sy(y) + 4} textAnchor="end">{y}</text>
          </g>
        ))}
        <text x={L} y={H - 6}>{label(x0)}</text>
        <text x={W - R} y={H - 6} textAnchor="end">{label(x1)}</text>
        {usable.map((s) => {
          const pts = [...s.points].sort((a, b) => a.x - b.x);
          const d = pts.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join("");
          const last = pts[pts.length - 1];
          return (
            <g key={s.name}>
              <path d={d} fill="none" stroke={s.color} strokeWidth={2.5} strokeLinejoin="round" />
              <circle cx={sx(last.x)} cy={sy(last.y)} r={3.5} fill={s.color}>
                <title>{`${s.name}: Level ${Math.floor(last.y)}`}</title>
              </circle>
            </g>
          );
        })}
      </svg>
      {usable.length > 1 && (
        <div className="legend">
          {usable.map((s) => (
            <span key={s.name}>
              <i style={{ background: s.color }} />
              {s.name}
            </span>
          ))}
        </div>
      )}
    </>
  );
}

export function AxisToggle({ axis, onChange }: { axis: Axis; onChange: (a: Axis) => void }) {
  return (
    <div className="seg" role="group" aria-label="x-Achse">
      <button aria-pressed={axis === "played"} onClick={() => onChange("played")}>Spielzeit</button>
      <button aria-pressed={axis === "calendar"} onClick={() => onChange("calendar")}>Kalender</button>
    </div>
  );
}
