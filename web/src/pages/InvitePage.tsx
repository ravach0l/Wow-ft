import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMe } from "../App";
import { api } from "../api";
import { storageSet, useApi } from "../hooks";

export default function InvitePage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const { reloadMe } = useMe();
  const { data, error } = useApi<{ id: number; name: string; member: boolean }>(`/api/invites/${code}`);
  const [busy, setBusy] = useState(false);

  async function join() {
    setBusy(true);
    const g = await api.post<{ id: number }>(`/api/invites/${code}/join`);
    storageSet("wowft.group", String(g.id));
    await reloadMe();
    navigate(`/g/${g.id}`);
  }

  if (error) return <div className="center"><p className="error">Diese Einladung gilt nicht (mehr).</p></div>;
  if (!data) return <p className="muted">Lädt …</p>;
  return (
    <div className="center">
      <div className="section">
        <h1 style={{ marginBottom: 10 }}>{data.name}</h1>
        {data.member ? (
          <>
            <p>Du bist schon in dieser Gruppe.</p>
            <button className="btn primary" onClick={() => navigate(`/g/${data.id}`)}>Zur Übersicht</button>
          </>
        ) : (
          <>
            <p>Du wurdest eingeladen. Alle in der Gruppe sehen die Charaktere der anderen.</p>
            <button className="btn primary" disabled={busy} onClick={join}>Beitreten</button>
          </>
        )}
      </div>
    </div>
  );
}
