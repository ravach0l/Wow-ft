import { useState } from "react";
import { useParams } from "react-router-dom";
import { XpBar } from "../components/CharacterCard";
import Chart, { AxisToggle, type Axis } from "../components/Chart";
import EventLine from "../components/EventLine";
import { useMe } from "../App";
import { ago, dateTime, duration, gold, number } from "../format";
import { useApi } from "../hooks";
import { hiddenLabels } from "../privacy";
import { talentGrid } from "../talents";
import type { CharacterDetailState, History, Skill, TalentTab } from "../types";
import { classColor, className, qualityColor, raceName } from "../wow";

export default function CharacterPage() {
  const { charId } = useParams();
  const { me } = useMe();
  const { data, error } = useApi<History>(`/api/characters/${charId}/history`);
  const [axisChoice, setAxis] = useState<Axis>("played");
  const [photoIdx, setPhotoIdx] = useState(0);

  if (error) return <p className="error">{error.message}</p>;
  if (!data) return <p className="muted">Lädt …</p>;
  const c = data.character;
  if (!c) return <p className="muted">Für diesen Charakter gibt es noch keine Daten.</p>;
  const color = classColor(c.class);
  // Ohne freigegebene Spielzeit gibt es nur die Kalenderachse.
  const paceHidden = data.hidden.includes("pace");
  const rateHidden = data.hidden.includes("rate");
  const axis: Axis = paceHidden ? "calendar" : axisChoice;
  const hiddenNames = hiddenLabels(data.hidden, me.features.race);
  const photo = data.photos[photoIdx] ?? data.photos[0];
  const points = data.snapshots
    .map((s) => ({ x: axis === "calendar" ? s.ts : s.playedTotal, y: s.level + (s.xpMax > 0 ? s.xp / s.xpMax : 0) }))
    .filter((p): p is { x: number; y: number } => p.x != null);

  return (
    <>
      <div className={`hero${photo ? " with-photo" : ""}`}>
        {photo && (
          <figure className="photo">
            <img src={photo.url} alt={`${c.name} mit Level ${photo.level ?? "?"}`} />
            <figcaption>{photo.level ? `Level ${photo.level} · ` : ""}{dateTime(photo.ts)}</figcaption>
          </figure>
        )}
        <div className="card">
          <div className="card-head">
            {!photo && <div className="avatar" style={{ color }} aria-hidden>{c.name.slice(0, 1)}</div>}
            <div className="who">
              <h1 className="cname" style={{ color }}>{c.name}</h1>
              <div className="meta">
                {raceName(c.race)} {className(c.class)} · {c.ownerName}
                {c.zone ? ` · ${c.zone}` : ""} · {ago(c.ts)}
              </div>
            </div>
            <div className="level">{c.level}<small>Level</small></div>
          </div>
          <XpBar c={c} />
          <div className="stats">
            {!rateHidden && (
              <>
                <Stat k="XP pro Stunde" v={number(c.xpPerHour)} />
                <Stat k="bis Level 60 (Spielzeit)" v={duration(c.etaSeconds)} />
              </>
            )}
            {!paceHidden && (
              <>
                <Stat k="Spielzeit gesamt" v={duration(c.playedTotal)} />
                <Stat k="Spielzeit im Level" v={duration(c.playedLevel)} />
              </>
            )}
            {c.deaths != null && <Stat k="Tode" v={number(c.deaths)} />}
            {c.gold != null && <Stat k="Gold" v={gold(c.gold)} />}
          </div>
        </div>
      </div>

      {hiddenNames.length > 0 && (
        <p className="muted" role="note">Nicht freigegeben: {hiddenNames.join(", ")}.</p>
      )}

      {data.photos.length > 1 && (
        <div className="gallery" aria-label="Ältere Bilder">
          {data.photos.map((p, i) => (
            <button key={p.id} aria-pressed={i === photoIdx} onClick={() => setPhotoIdx(i)}>
              <img src={p.url} alt="" loading="lazy" />
              <span>{p.level ? `Lv ${p.level}` : dateTime(p.ts)}</span>
            </button>
          ))}
        </div>
      )}

      <div className="section">
        <div className="toolbar" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Level-Verlauf</h2>
          {!paceHidden && <AxisToggle axis={axis} onChange={setAxis} />}
        </div>
        <Chart series={[{ name: c.name, color: "var(--accent)", points }]} axis={axis} />
      </div>

      <StateSections state={data.state} />

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

function StateSections({ state }: { state: CharacterDetailState }) {
  const groups: [Skill["category"], string][] = [
    ["profession", "Berufe"],
    ["secondary", "Sekundäre Fertigkeiten"],
    ["weapon", "Waffenfertigkeiten"],
  ];
  const mats = state.materials;
  return (
    <div className="columns">
      {state.equipment.length > 0 && (
        <div className="section">
          <h2>Ausrüstung</h2>
          <ul className="list compact">
            {state.equipment.map((e) => (
              <li key={e.slot}>
                <span className="muted slot">{e.slotName}</span>
                <span style={{ color: qualityColor(e.quality) }}>{e.name ?? "?"}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {state.skills.length > 0 && (
        <div className="section">
          {groups.map(([cat, title]) => {
            const list = state.skills.filter((s) => s.category === cat);
            if (list.length === 0) return null;
            return (
              <div key={cat} style={{ marginBottom: 14 }}>
                <h2>{title}</h2>
                {list.map((s) => (
                  <Meter key={s.name} label={s.name} value={s.rank} max={s.max || 300} />
                ))}
              </div>
            );
          })}
        </div>
      )}

      {state.talents.some((t) => t.points > 0) && (
        <div className="section">
          <h2>Talente</h2>
          <p style={{ color: "var(--text)" }}>{state.talents.map((t) => t.points).join(" / ")}</p>
          <div className="trees">
            {state.talents
              .filter((t) => t.talents.length > 0)
              .map((t) => <TalentTree key={t.name ?? ""} tab={t} />)}
          </div>
        </div>
      )}

      {state.reputation.length > 0 && (
        <div className="section">
          <h2>Ruf</h2>
          {state.reputation.map((r) => (
            <Meter
              key={r.id ?? r.name}
              label={`${r.name} · ${r.standingName}`}
              value={(r.value ?? 0) - (r.min ?? 0)}
              max={Math.max(1, (r.max ?? 1) - (r.min ?? 0))}
              showNumbers={false}
            />
          ))}
        </div>
      )}

      {mats && (mats.bags.length > 0 || (mats.bank?.length ?? 0) > 0) && (
        <div className="section">
          <h2>Handwerksmaterialien</h2>
          <ul className="list compact">
            {mergeMaterials(mats.bags, mats.bank ?? []).map((m) => (
              <li key={m.id}>
                <span>{m.name ?? `Item ${m.id}`}</span>
                <span className="when">{number(m.bags + m.bank)}</span>
              </li>
            ))}
          </ul>
          <p className="muted" style={{ marginTop: 8, marginBottom: 0 }}>
            Bank zuletzt gelesen: {mats.bankScanned ? ago(mats.bankScanned) : "nie"}
          </p>
        </div>
      )}
    </div>
  );
}

export function mergeMaterials(
  bags: { id: number; name: string | null; count: number }[],
  bank: { id: number; name: string | null; count: number }[],
) {
  const out = new Map<number, { id: number; name: string | null; bags: number; bank: number }>();
  for (const [list, key] of [[bags, "bags"], [bank, "bank"]] as const) {
    for (const m of list) {
      const e = out.get(m.id) ?? { id: m.id, name: m.name, bags: 0, bank: 0 };
      e[key] += m.count;
      e.name = e.name ?? m.name;
      out.set(m.id, e);
    }
  }
  return [...out.values()].sort((a, b) => (a.name ?? "").localeCompare(b.name ?? ""));
}

function TalentTree({ tab }: { tab: TalentTab }) {
  const grid = talentGrid(tab.talents);
  return (
    <figure className="tree">
      <figcaption className="meta">{tab.name} ({tab.points})</figcaption>
      <div
        className="tree-grid"
        role="list"
        style={{ gridTemplateColumns: `repeat(${grid.cols}, 52px)`, gridTemplateRows: `repeat(${grid.rows}, auto)` }}
      >
        {grid.cells.map(({ talent: x, row, col }) => {
          const full = x.max != null && x.rank >= x.max;
          const state = x.rank === 0 ? "none" : full ? "full" : "part";
          return (
            <div
              key={`${row}-${col}-${x.name}`}
              role="listitem"
              className={`talent ${state}`}
              style={{ gridRow: row + 1, gridColumn: col + 1 }}
              title={`${x.name} ${x.rank}/${x.max ?? "?"}`}
            >
              <span className="tname">{x.name}</span>
              <span className="trank">{x.rank}/{x.max ?? "?"}</span>
            </div>
          );
        })}
      </div>
    </figure>
  );
}

function Meter({ label, value, max, showNumbers = true }: { label: string; value: number; max: number; showNumbers?: boolean }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="meter">
      <div className="row">
        <span style={{ color: "var(--text)" }}>{label}</span>
        {showNumbers && <span>{value} / {max}</span>}
      </div>
      <div className="bar thin"><span className="xp" style={{ width: `${pct}%` }} /></div>
    </div>
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
