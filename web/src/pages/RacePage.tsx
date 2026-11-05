import { useState } from "react";
import { useParams } from "react-router-dom";
import Chart, { AxisToggle, type Axis, type Series } from "../components/Chart";
import { useApi } from "../hooks";
import type { RaceSeries } from "../types";
import { classColor } from "../wow";

export function toSeries(race: RaceSeries[], axis: Axis): Series[] {
  return race.map((r) => ({
    name: r.name,
    color: classColor(r.class),
    points: r.points
      .map(([ts, played, y]) => ({ x: axis === "calendar" ? ts : played, y }))
      .filter((p): p is { x: number; y: number } => p.x != null),
  }));
}

export default function RacePage() {
  const { groupId } = useParams();
  const { data, error } = useApi<RaceSeries[]>(`/api/groups/${groupId}/race`);
  const [axis, setAxis] = useState<Axis>("played");
  if (error) return <p className="error">{error.message}</p>;
  if (!data) return <p className="muted">Lädt …</p>;
  return (
    <div className="section">
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>Level-Rennen</h2>
        <AxisToggle axis={axis} onChange={setAxis} />
      </div>
      <p>
        {axis === "played"
          ? "Nach Spielzeit: fair für alle, die weniger Zeit haben."
          : "Nach Kalender: zeigt, wer gerade aktiv ist."}
      </p>
      <Chart series={toSeries(data, axis)} axis={axis} height={300} />
    </div>
  );
}
