import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { FACTION_NAMES, planDungeons, suggestions, type DungeonPlan, type FactionPlan } from "../dungeons";
import { storageGet, storageSet, useApi } from "../hooks";
import type { PlannerCharacter, PlannerData } from "../types";
import { classColor } from "../wow";

export default function DungeonsPage() {
  const { groupId } = useParams();
  const { data, error } = useApi<PlannerData>(`/api/groups/${groupId}/dungeons`);
  const [showAll, setShowAll] = useState(() => storageGet("wowft.dungeonsAll") === "1");

  if (error) return <p className="error">{error.message}</p>;
  if (!data) return <p className="muted">Lädt …</p>;

  const plans = planDungeons(data.dungeons, data.characters, showAll);
  const top = suggestions(planDungeons(data.dungeons, data.characters));
  const dungeons = plans.filter((p) => !p.dungeon.raid);
  const raids = plans.filter((p) => p.dungeon.raid);

  function toggle(v: boolean) {
    setShowAll(v);
    storageSet("wowft.dungeonsAll", v ? "1" : "0");
  }

  return (
    <>
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <h1>Dungeons</h1>
        <label className="toggle">
          <input type="checkbox" checked={showAll} onChange={(e) => toggle(e.target.checked)} />
          alle zeigen
        </label>
      </div>

      {top.length > 0 && (
        <div className="section">
          <h2>Passt gerade gut</h2>
          <ul className="list compact">
            {top.map((p) => {
              const f = p.factions[0];
              return (
                <li key={p.dungeon.key}>
                  <a href={`#${p.dungeon.key}`} style={{ fontWeight: 600 }}>{p.dungeon.name}</a>
                  <span className="when">
                    {f.people} {f.people === 1 ? "Person" : "Personen"} · {FACTION_NAMES[f.faction] ?? f.faction}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {plans.length === 0 && (
        <div className="section">
          <p>Gerade passt niemand in einen Dungeon. Mit „alle zeigen“ siehst du die ganze Liste.</p>
        </div>
      )}

      <div className="grid">
        {dungeons.map((p) => <DungeonCard key={p.dungeon.key} plan={p} />)}
      </div>

      {raids.length > 0 && (
        <>
          <h2 style={{ margin: "20px 0 12px" }}>Schlachtzüge</h2>
          <div className="grid">
            {raids.map((p) => <DungeonCard key={p.dungeon.key} plan={p} />)}
          </div>
        </>
      )}

      <p className="muted" style={{ marginTop: 16 }}>
        Stufenbereiche nach Classic; „bald“ heißt bis zu 3 Level darunter. Allianz und Horde werden getrennt
        gezählt, weil sie nicht zusammen spielen können. ✓ = dort schon einen Boss besiegt.
      </p>
    </>
  );
}

function DungeonCard({ plan }: { plan: DungeonPlan }) {
  const d = plan.dungeon;
  return (
    <div className="card dungeon" id={d.key}>
      <div className="row" style={{ alignItems: "baseline" }}>
        <b style={{ color: "var(--text)", fontSize: "1rem" }}>{d.name}</b>
        <span>{d.min === d.max ? `Stufe ${d.min}` : `${d.min}–${d.max}`}</span>
      </div>
      <div className="meta">
        {d.zone}
        {d.raid ? ` · Schlachtzug (${d.size})` : ""}
      </div>
      {plan.factions.length === 0 && <p className="muted" style={{ margin: "8px 0 0" }}>Niemand im passenden Bereich.</p>}
      {plan.factions.map((f) => (
        <FactionRow key={f.faction} plan={f} dungeonKey={d.key} showFaction={plan.factions.length > 1} />
      ))}
    </div>
  );
}

function FactionRow({ plan, dungeonKey, showFaction }: { plan: FactionPlan; dungeonKey: string; showFaction: boolean }) {
  return (
    <div className="dungeon-faction">
      {showFaction && <div className="meta">{FACTION_NAMES[plan.faction] ?? plan.faction}</div>}
      {plan.fit.length > 0 && (
        <div className="chips">
          <span className="chip-label">{plan.people} {plan.people === 1 ? "passt" : "passen"}:</span>
          {plan.fit.map((c) => <Chip key={c.id} c={c} dungeonKey={dungeonKey} />)}
        </div>
      )}
      {plan.soon.length > 0 && (
        <div className="chips soon">
          <span className="chip-label">bald:</span>
          {plan.soon.map((c) => <Chip key={c.id} c={c} dungeonKey={dungeonKey} />)}
        </div>
      )}
      {plan.fit.length > 0 && plan.over.length > 0 && (
        <div className="chips over">
          <span className="chip-label">könnten helfen:</span>
          {plan.over.map((c) => <Chip key={c.id} c={c} dungeonKey={dungeonKey} />)}
        </div>
      )}
    </div>
  );
}

function Chip({ c, dungeonKey }: { c: PlannerCharacter; dungeonKey: string }) {
  const done = c.cleared.includes(dungeonKey);
  return (
    <Link
      to={`/c/${c.id}`}
      className="chip"
      title={`${c.name} (${c.ownerName}), Level ${c.level}${done ? ", dort schon einen Boss besiegt" : ""}`}
    >
      <span style={{ color: classColor(c.class) }}>{c.name}</span> <b>{c.level}</b>
      {done && <span className="done" aria-label="schon besiegt"> ✓</span>}
    </Link>
  );
}
