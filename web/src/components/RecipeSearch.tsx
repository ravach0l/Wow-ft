import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { number } from "../format";
import type { RecipeResult } from "../types";
import { classColor } from "../wow";

/** „Wer kann was?“: Rezepte der Gruppe suchen, mit Herstellern und Reagenzien-Beständen. */
export default function RecipeSearch({ groupId, onWished }: { groupId: string; onWished: () => void }) {
  const [q, setQ] = useState("");
  const [data, setData] = useState<{ known: number; results: RecipeResult[] } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    const t = window.setTimeout(async () => {
      try {
        setData(await api.get(`/api/groups/${groupId}/recipes?q=${encodeURIComponent(q.trim())}`));
      } catch (e) {
        setMsg((e as Error).message);
      }
    }, 250);
    return () => window.clearTimeout(t);
  }, [groupId, q]);

  async function wish(name: string, count: number) {
    await api.post(`/api/groups/${groupId}/requests`, { itemName: name, count });
    setMsg(`Wunsch eingetragen: ${count}× ${name}`);
    onWished();
  }

  return (
    <div className="section">
      <h2>Rezepte</h2>
      <p>
        Wer kann was herstellen, und wer hat die Zutaten? Das Addon erfasst die Rezepte, sobald man im Spiel
        das Berufsfenster öffnet{data ? ` (bisher ${number(data.known)} bekannt)` : ""}.
      </p>
      <input
        type="text"
        placeholder="Rezept suchen, z. B. Kupfer"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        style={{ width: "100%", marginBottom: 12 }}
        aria-label="Rezept suchen"
      />
      {q.trim().length >= 2 && data && data.results.length === 0 && <p className="muted">Kein Rezept gefunden.</p>}
      <ul className="list">
        {data?.results.map((r) => (
          <li key={r.name} style={{ flexDirection: "column", alignItems: "stretch", gap: 6 }}>
            <div className="row" style={{ color: "var(--text)" }}>
              <b>{r.name}</b>
              <span className="muted">{r.profession}</span>
            </div>
            <div className="chips">
              <span className="chip-label">können:</span>
              {r.crafters.map((c) => (
                <Link key={c.characterId} to={`/c/${c.characterId}`} className="chip" title={c.ownerName}>
                  <span style={{ color: classColor(c.class) }}>{c.name}</span>
                </Link>
              ))}
            </div>
            {r.reagents.map((g) => (
              <div className="row reagent" key={`${g.id}-${g.name}`}>
                <span>
                  {g.count}× {g.name ?? `Item ${g.id}`}
                  {g.holders.length > 0 ? (
                    <span className="muted"> · {g.holders.map((h) => `${h.name} ${number(h.count)}`).join(", ")}</span>
                  ) : (
                    <span className="muted"> · hat niemand (bekannt)</span>
                  )}
                </span>
                {g.total < g.count && g.name && (
                  <button className="btn small" onClick={() => wish(g.name!, g.count - g.total)}>
                    suchen
                  </button>
                )}
              </div>
            ))}
          </li>
        ))}
      </ul>
      {msg && <p className="meta">{msg}</p>}
    </div>
  );
}
