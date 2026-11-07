import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ago, number } from "../format";
import { api } from "../api";
import { useApi } from "../hooks";
import type { MaterialItem, MaterialRequest } from "../types";
import { classColor } from "../wow";

export default function MaterialsPage() {
  const { groupId } = useParams();
  const { data, error } = useApi<MaterialItem[]>(`/api/groups/${groupId}/materials`);
  const requests = useApi<MaterialRequest[]>(`/api/groups/${groupId}/requests`);
  const [q, setQ] = useState("");
  if (error) return <p className="error">{error.message}</p>;
  if (!data) return <p className="muted">Lädt …</p>;
  const needle = q.trim().toLowerCase();
  const items = needle ? data.filter((i) => (i.name ?? "").toLowerCase().includes(needle)) : data;
  const wanted = (i: MaterialItem) =>
    (requests.data ?? []).filter(
      (r) => (r.itemId != null && r.itemId === i.id) || r.itemName.toLowerCase() === (i.name ?? "").toLowerCase(),
    );

  return (
    <>
    <Requests
      groupId={groupId!}
      requests={requests.data}
      knownNames={data.map((i) => i.name).filter((n): n is string => !!n)}
      reload={requests.reload}
    />
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
                <b>
                  {i.name ?? `Item ${i.id}`}
                  {wanted(i).map((r) => (
                    <span key={r.id} className="badge" title={`${r.userName} sucht ${r.count}`}>
                      gesucht von {r.userName}
                    </span>
                  ))}
                </b>
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
    </>
  );
}

function Requests({
  groupId,
  requests,
  knownNames,
  reload,
}: {
  groupId: string;
  requests: MaterialRequest[] | null;
  knownNames: string[];
  reload: () => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [count, setCount] = useState(1);
  const [msg, setMsg] = useState<string | null>(null);

  async function add(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.post(`/api/groups/${groupId}/requests`, { itemName: name.trim(), count });
      setName("");
      setCount(1);
      setMsg(null);
      reload();
    } catch (err) {
      setMsg((err as Error).message);
    }
  }
  async function act(id: number, how: "done" | "delete") {
    if (how === "done") await api.post(`/api/requests/${id}/done`);
    else await api.del(`/api/requests/${id}`);
    reload();
  }

  return (
    <div className="section">
      <h2>Gesucht</h2>
      {requests && requests.length > 0 ? (
        <ul className="list">
          {requests.map((r) => (
            <li key={r.id} style={{ flexDirection: "column", alignItems: "stretch", gap: 4 }}>
              <div className="row" style={{ color: "var(--text)" }}>
                <span>
                  <b>{number(r.count)}× {r.itemName}</b> <span className="muted">· {r.mine ? "von dir" : r.userName}</span>
                </span>
                {r.canManage && (
                  <span style={{ display: "flex", gap: 6 }}>
                    <button className="btn small" onClick={() => act(r.id, "done")}>Erledigt</button>
                    <button className="btn small danger" onClick={() => act(r.id, "delete")} aria-label="Wunsch löschen">✕</button>
                  </span>
                )}
              </div>
              {r.holders.length > 0 ? (
                <div className="chips">
                  <span className="chip-label">haben:</span>
                  {r.holders.map((h) => (
                    <Link key={h.characterId} to={`/c/${h.characterId}`} className="chip" title={h.ownerName}>
                      <span style={{ color: classColor(h.class) }}>{h.name}</span> <b>{number(h.count)}</b>
                    </Link>
                  ))}
                </div>
              ) : (
                <span className="meta">Hat in der Gruppe gerade niemand (soweit bekannt).</span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p>Noch keine Wünsche. Trag ein, was du suchst; wer es hat, sieht es hier{requests ? "" : " …"}.</p>
      )}
      <form className="inline-form" onSubmit={add} style={{ marginTop: 12 }}>
        <input
          type="text"
          list="known-materials"
          placeholder="Was suchst du? z. B. Kupferbarren"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={150}
          aria-label="Material"
        />
        <datalist id="known-materials">
          {knownNames.map((n) => <option key={n} value={n} />)}
        </datalist>
        <input
          type="number"
          min={1}
          max={9999}
          value={count}
          onChange={(e) => setCount(Math.max(1, Number(e.target.value) || 1))}
          aria-label="Anzahl"
          style={{ width: "5.5em", minWidth: 0, flex: "none" }}
        />
        <button className="btn primary" type="submit">Suchen</button>
      </form>
      <p className="meta" style={{ margin: "8px 0 0" }}>Wünsche laufen nach 7 Tagen ab. Mit Discord-Webhook geht ein Hinweis in den Kanal.</p>
      {msg && <p className="error">{msg}</p>}
    </div>
  );
}

