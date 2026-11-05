import { useState } from "react";
import { useParams } from "react-router-dom";
import { XpBar } from "../components/CharacterCard";
import EventLine from "../components/EventLine";
import LevelChart from "../components/LevelChart";
import { ago, duration, gold, number } from "../format";
import { useApi } from "../hooks";
import type { History } from "../types";
import { classColor, className, raceName } from "../wow";

export default function CharacterPage() {
  const { charId } = useParams();
  const { data, error } = useApi<History>(`/api/characters/${charId}/history`);
  const [axis, setAxis] = useState<"calendar" | "played">("played");

  if (error) return <p className="error">{error.message}</p>;
  if (!data) return <p className="muted">Lädt …</p>;
  const c = data.character;
  if (!c) return <p className="muted">Für diesen Charakter gibt es noch keine Daten.</p>;

  return (
    <>
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-head">
          <div className="avatar" style={{ color: classColor(c.class) }} aria-hidden>{c.name.slice(0, 1)}</div>
          <div className="who">
            <h1 className="cname" style={{ color: classColor(c.class) }}>{c.name}</h1>
            <div className="meta">
              {raceName(c.race)} {className(c.class)} · {c.ownerName}
              {c.zone ? ` · ${c.zone}` : ""} · {ago(c.ts)}
            </div>
          </div>
          <div className="level">{c.level}<small>Level</small></div>
        </div>
        <XpBar c={c} />
      </div>

      <div className="stats">
        <Stat k="XP pro Stunde" v={number(c.xpPerHour)} />
        <Stat k="bis Level 60 (Spielzeit)" v={duration(c.etaSeconds)} />
        <Stat k="Spielzeit gesamt" v={duration(c.playedTotal)} />
        <Stat k="Spielzeit im Level" v={duration(c.playedLevel)} />
        {c.gold != null && <Stat k="Gold" v={gold(c.gold)} />}
      </div>

      <div className="section">
        <div className="toolbar" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Level-Verlauf</h2>
          <div className="seg" role="group" aria-label="x-Achse">
            <button aria-pressed={axis === "played"} onClick={() => setAxis("played")}>Spielzeit</button>
            <button aria-pressed={axis === "calendar"} onClick={() => setAxis("calendar")}>Kalender</button>
          </div>
        </div>
        <LevelChart snapshots={data.snapshots} axis={axis} />
      </div>

      <div className="section">
        <h2>Ereignisse</h2>
        {data.events.length === 0 ? (
          <p>Noch keine.</p>
        ) : (
          <ul className="list">
            {data.events.map((e) => <EventLine key={e.id} e={e} showName={false} />)}
          </ul>
        )}
      </div>
    </>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div className="stat">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
    </div>
  );
}
