import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ago, number } from "../format";
import { useApi } from "../hooks";
import type { MaterialItem } from "../types";
import { classColor } from "../wow";

export default function MaterialsPage() {
  const { groupId } = useParams();
  const { data, error } = useApi<MaterialItem[]>(`/api/groups/${groupId}/materials`);
  const [q, setQ] = useState("");
  if (error) return <p className="error">{error.message}</p>;
  if (!data) return <p className="muted">Lädt …</p>;
  const needle = q.trim().toLowerCase();
  const items = needle ? data.filter((i) => (i.name ?? "").toLowerCase().includes(needle)) : data;

  return (
    <div className="section">
      <h2>Handwerksmaterialien</h2>
      <p>Taschen und letzter bekannter Bankstand. Die Bank wird nur beim Öffnen im Spiel gelesen.</p>
      <input
        type="text"
        placeholder="Suchen, z. B. Kupfererz"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        style={{ width: "100%", marginBottom: 12 }}
        aria-label="Material suchen"
      />
      {items.length === 0 ? (
        <p className="muted">{data.length === 0 ? "Noch keine Materialdaten." : "Nichts gefunden."}</p>
      ) : (
        <ul className="list">
          {items.map((i) => (
            <li key={i.id} style={{ flexDirection: "column", alignItems: "stretch", gap: 4 }}>
              <div className="row" style={{ color: "var(--text)" }}>
                <b>{i.name ?? `Item ${i.id}`}</b>
                <b>{number(i.total)}</b>
              </div>
              {i.holders.map((h) => (
                <div className="row" key={h.characterId}>
                  <span>
                    <Link to={`/c/${h.characterId}`} style={{ color: classColor(h.class) }}>{h.name}</Link>{" "}
                    <span className="muted">({h.ownerName})</span>
                  </span>
                  <span title={h.bankScanned ? `Bank gelesen ${ago(h.bankScanned)}` : "Bank noch nie gelesen"}>
                    {h.bags > 0 && `${number(h.bags)} Taschen`}
                    {h.bags > 0 && h.bank > 0 && " · "}
                    {h.bank > 0 && `${number(h.bank)} Bank`}
                  </span>
                </div>
              ))}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
