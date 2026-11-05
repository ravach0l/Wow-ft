import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMe } from "../App";
import CharacterCard from "../components/CharacterCard";
import Freshness from "../components/Freshness";
import { storageGet, storageSet, useApi } from "../hooks";
import { groupByOwner, SORT_LABELS, type SortMode } from "../sort";
import type { Overview } from "../types";

export default function OverviewPage() {
  const { groupId } = useParams();
  const { me } = useMe();
  const navigate = useNavigate();
  const { data, error, reload } = useApi<Overview>(`/api/groups/${groupId}/overview`);
  const [mode, setMode] = useState<SortMode>(() => (storageGet("wowft.sort") as SortMode) || "level");

  useEffect(() => {
    if (groupId) storageSet("wowft.group", groupId);
  }, [groupId]);

  useEffect(() => {
    const t = window.setInterval(reload, 60_000);
    return () => window.clearInterval(t);
  }, [reload]);

  function choose(m: SortMode) {
    setMode(m);
    storageSet("wowft.sort", m);
  }

  if (error) return <p className="error">{error.message}</p>;
  if (!data) return <p className="muted">Lädt …</p>;

  // Die Spielzeit ist für andere nur im Rennen-Modus sichtbar; ohne ihn entfällt diese Sortierung.
  const available = (Object.keys(SORT_LABELS) as SortMode[]).filter((m) => m !== "played" || me.features.race);
  const active: SortMode = available.includes(mode) ? mode : "level";
  const people = groupByOwner(data.characters, active);

  return (
    <>
      <Freshness lastUpload={data.lastUpload} />
      <div className="toolbar">
        {me.groups.length > 1 ? (
          <select value={groupId} onChange={(e) => navigate(`/g/${e.target.value}`)} aria-label="Gruppe">
            {me.groups.map((g) => (
              <option key={g.id} value={g.id}>{g.name}</option>
            ))}
          </select>
        ) : (
          <h1>{data.group.name}</h1>
        )}
        {available.length > 1 && (
          <div className="seg" role="group" aria-label="Sortierung">
            {available.map((m) => (
              <button key={m} aria-pressed={active === m} onClick={() => choose(m)}>
                {SORT_LABELS[m]}
              </button>
            ))}
          </div>
        )}
      </div>

      {people.length === 0 ? (
        <div className="section">
          <p>Hier ist noch niemand. Unter <Link to="/profil">Profil</Link> findest du den Upload-Token und den Einladungslink.</p>
        </div>
      ) : (
        <div className="grid">
          {people.map((p) => (
            <div className="person" key={p.ownerId}>
              <CharacterCard c={p.main} />
              {p.twinks.length > 0 && (
                <details className="twinks">
                  <summary>
                    {p.ownerName}: {p.twinks.length} weitere{p.twinks.length === 1 ? "r" : ""} Charakter
                    {p.twinks.length === 1 ? "" : "e"}
                  </summary>
                  {p.twinks.map((t) => (
                    <CharacterCard key={t.id} c={t} compact />
                  ))}
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
