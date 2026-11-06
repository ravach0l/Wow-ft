import { useState, type FormEvent } from "react";
import { useMe } from "../App";
import { api } from "../api";
import { ago } from "../format";
import { useApi } from "../hooks";
import { SHARE_CATEGORIES } from "../privacy";
import type { GroupDetail, OwnCharacter, UploadToken } from "../types";
import { classColor, className } from "../wow";

export default function ProfilePage() {
  const { me } = useMe();
  return (
    <>
      <h1 style={{ marginBottom: 16 }}>Profil</h1>
      <Groups />
      <Tokens />
      <Characters />
      <ManualUpload />
      {me.isAdmin && <AdminFeatures />}
      <div className="section">
        <h2>Abmelden</h2>
        <p>Angemeldet als {me.name}.</p>
        <button
          className="btn"
          onClick={async () => {
            await api.post("/auth/logout");
            window.location.href = "/";
          }}
        >
          Abmelden
        </button>
      </div>
    </>
  );
}

function Tokens() {
  const { data, reload } = useApi<UploadToken[]>("/api/tokens");
  const [name, setName] = useState("");
  const [fresh, setFresh] = useState<string | null>(null);

  async function create(e: FormEvent) {
    e.preventDefault();
    const t = await api.post<UploadToken>("/api/tokens", { name: name || "Spielrechner" });
    setFresh(t.token ?? null);
    setName("");
    reload();
  }

  async function revoke(id: number) {
    if (!confirm("Token widerrufen? Der Uploader mit diesem Token kann danach nichts mehr senden.")) return;
    await api.del(`/api/tokens/${id}`);
    reload();
  }

  const active = data?.filter((t) => !t.revoked) ?? [];

  return (
    <div className="section">
      <h2>Uploader einrichten</h2>
      <ol className="steps">
        <li>Addon <code>WowFT</code> in <code>Interface/AddOns</code> kopieren, einloggen.</li>
        <li>Hier einen Upload-Token erzeugen.</li>
        <li>Uploader starten, Token einfügen, WoW-Ordner bestätigen.</li>
        <li>Nach jedem Logout oder <code>/reload</code> landet der Stand hier.</li>
      </ol>
      <form className="inline-form" onSubmit={create} style={{ marginTop: 14 }}>
        <input type="text" placeholder="Name, z. B. Spiele-PC" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} />
        <button className="btn primary" type="submit">Token erzeugen</button>
      </form>
      {fresh && (
        <>
          <div className="secret">{fresh}</div>
          <p>
            Wird nur jetzt angezeigt.{" "}
            <button className="btn small" onClick={() => navigator.clipboard?.writeText(fresh)}>Kopieren</button>
          </p>
        </>
      )}
      {active.length > 0 && (
        <ul className="list">
          {active.map((t) => (
            <li key={t.id}>
              <span>
                {t.name} <span className="muted">{t.prefix}…</span>
              </span>
              <span className="when">zuletzt benutzt {ago(t.lastUsed)}</span>
              <button className="btn small danger" onClick={() => revoke(t.id)}>Widerrufen</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Characters() {
  const { me } = useMe();
  const { data, reload } = useApi<OwnCharacter[]>("/api/me/characters");
  async function patch(id: number, body: { visible?: boolean; share?: Record<string, boolean> }) {
    await api.patch(`/api/characters/${id}`, body);
    reload();
  }
  if (!data || data.length === 0) return null;
  return (
    <div className="section">
      <h2>Meine Charaktere</h2>
      <ul className="list">
        {data.map((c) => (
          <li key={c.id} style={{ flexWrap: "wrap" }}>
            <span style={{ color: classColor(c.class), fontWeight: 600 }}>{c.name}</span>
            <span className="muted">{className(c.class)}</span>
            <span className="when">Upload {ago(c.lastUpload)}</span>
            <div style={{ width: "100%" }}>
              <label className="toggle">
                <input type="checkbox" checked={c.visible} onChange={(e) => patch(c.id, { visible: e.target.checked })} />
                in Gruppen zeigen
              </label>
            </div>
            {c.visible && (
              <details className="shares">
                <summary>Was sehen die anderen?</summary>
                <p className="muted" style={{ margin: "8px 0" }}>
                  Level und XP sind immer sichtbar. Du selbst siehst von deinen Charakteren immer alles.
                  Gold und Tempo sind standardmäßig aus. Aus dem Tempo (XP pro Stunde) und dem Level lässt sich
                  deine Spielzeit ungefähr errechnen.
                </p>
                <div className="share-grid">
                  {SHARE_CATEGORIES.map((cat) => (
                    <label className="toggle" key={cat.key} title={cat.hint}>
                      <input
                        type="checkbox"
                        checked={c.share[cat.key] ?? false}
                        onChange={(e) => patch(c.id, { share: { [cat.key]: e.target.checked } })}
                      />
                      {cat.label}
                    </label>
                  ))}
                </div>
                {!me.features.race && (
                  <p className="muted" style={{ margin: "8px 0 0" }}>
                    Deine Spielzeit sehen andere erst, wenn ein Admin den Rennen-Modus einschaltet. Bis dahin
                    bleibt sie verborgen, egal wie du hier einstellst.
                  </p>
                )}
              </details>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Groups() {
  const { me, reloadMe } = useMe();
  const [name, setName] = useState("");

  async function create(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await api.post("/api/groups", { name: name.trim() });
    setName("");
    reloadMe();
  }

  return (
    <div className="section">
      <h2>Gruppen</h2>
      {me.groups.length === 0 && <p>Du bist noch in keiner Gruppe. Leg eine an oder öffne einen Einladungslink.</p>}
      {me.groups.map((g) => (
        <GroupAdmin key={g.id} id={g.id} />
      ))}
      <form className="inline-form" onSubmit={create} style={{ marginTop: 12 }}>
        <input type="text" placeholder="Name der neuen Gruppe" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} />
        <button className="btn" type="submit">Gruppe anlegen</button>
      </form>
    </div>
  );
}

function GroupAdmin({ id }: { id: number }) {
  const { me, reloadMe } = useMe();
  const { data, reload } = useApi<GroupDetail>(`/api/groups/${id}`);
  if (!data) return null;
  const link = data.inviteCode ? `${window.location.origin}/invite/${data.inviteCode}` : null;

  async function rotate() {
    if (!confirm("Neuen Link erzeugen? Der alte funktioniert dann nicht mehr.")) return;
    await api.post(`/api/groups/${id}/invite`);
    reload();
  }
  async function remove(userId: number) {
    const self = userId === me.id;
    if (!confirm(self ? "Gruppe verlassen?" : "Mitglied entfernen?")) return;
    await api.del(`/api/groups/${id}/members/${userId}`).catch((e: Error) => alert(e.message));
    if (self) reloadMe();
    else reload();
  }

  return (
    <div className="card" style={{ marginBottom: 10 }}>
      <div className="cname">{data.name}</div>
      <div className="meta">{data.members.map((m) => m.name + (m.role === "owner" ? " (Leitung)" : "")).join(", ")}</div>
      {link && (
        <>
          <div className="secret">{link}</div>
          <div className="inline-form">
            <button className="btn small" onClick={() => navigator.clipboard?.writeText(link)}>Link kopieren</button>
            <button className="btn small" onClick={rotate}>Neuen Link erzeugen</button>
          </div>
        </>
      )}
      {data.role === "owner" && data.members.length > 1 && (
        <ul className="list">
          {data.members
            .filter((m) => m.id !== me.id)
            .map((m) => (
              <li key={m.id}>
                <span>{m.name}</span>
                <button className="btn small danger" style={{ marginLeft: "auto" }} onClick={() => remove(m.id)}>Entfernen</button>
              </li>
            ))}
        </ul>
      )}
      {data.role === "owner" && <DiscordSetting group={data} onSaved={reload} />}
      {data.role !== "owner" && (
        <button className="btn small danger" style={{ marginTop: 10 }} onClick={() => remove(me.id)}>Gruppe verlassen</button>
      )}
    </div>
  );
}

function ManualUpload() {
  const [msg, setMsg] = useState<string | null>(null);
  async function upload(file: File) {
    const form = new FormData();
    form.append("file", file);
    try {
      const r = await api.post<{ characters: number; snapshots: number }>("/api/me/upload", form);
      setMsg(`${r.characters} Charakter(e), ${r.snapshots} neue Snapshots übernommen.`);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }
  return (
    <div className="section">
      <h2>Datei von Hand hochladen</h2>
      <p>
        Ohne Uploader: <code>WTF/Account/&lt;NAME&gt;/SavedVariables/WowFT.lua</code> auswählen.
      </p>
      <input type="file" accept=".lua" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
      {msg && <p style={{ marginTop: 10 }}>{msg}</p>}
    </div>
  );
}

function DiscordSetting({ group, onSaved }: { group: GroupDetail; onSaved: () => void }) {
  const [url, setUrl] = useState(group.discordWebhook ?? "");
  const [msg, setMsg] = useState<string | null>(null);
  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      await api.patch(`/api/groups/${group.id}`, { discordWebhook: url.trim() });
      setMsg(url.trim() ? "Gespeichert. Neue Ereignisse landen im Kanal." : "Discord ausgeschaltet.");
      onSaved();
    } catch (err) {
      setMsg((err as Error).message);
    }
  }
  return (
    <form onSubmit={save} style={{ marginTop: 12 }}>
      <div className="meta" style={{ marginBottom: 6 }}>
        Discord-Webhook (Kanal → Einstellungen → Integrationen → Webhooks)
      </div>
      <div className="inline-form">
        <input type="text" placeholder="https://discord.com/api/webhooks/…" value={url} onChange={(e) => setUrl(e.target.value)} />
        <button className="btn small" type="submit">Speichern</button>
      </div>
      {msg && <p className="meta" style={{ marginTop: 6 }}>{msg}</p>}
    </form>
  );
}

function AdminFeatures() {
  const { reloadMe } = useMe();
  const { data } = useApi<{ key: string; label: string; enabled: boolean }[]>("/api/admin/features");
  const [state, setState] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  async function toggle(key: string, on: boolean) {
    setState((s) => ({ ...s, [key]: on }));
    try {
      await api.patch("/api/admin/features", { [key]: on });
      setError(null);
      await reloadMe();
    } catch (e) {
      setState((s) => ({ ...s, [key]: !on }));
      setError((e as Error).message);
    }
  }
  if (!data) return null;
  return (
    <div className="section">
      <h2>Admin: Module</h2>
      <p>Gilt für die ganze Seite und alle Gruppen. Ausgeschaltete Module sind für niemanden sichtbar.</p>
      {data.map((f) => (
        <label key={f.key} className="toggle" style={{ marginBottom: 8 }}>
          <input type="checkbox" checked={state[f.key] ?? f.enabled} onChange={(e) => toggle(f.key, e.target.checked)} />
          {f.label}
        </label>
      ))}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
