import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";

interface PairInfo {
  userCode: string;
  deviceName: string | null;
  approved: boolean;
  expiresIn: number;
}

/** Bestätigt einen Uploader, der gerade einen Code anzeigt (Gerätekopplung). */
export default function PairPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const code = params.get("code") ?? "";
  const [input, setInput] = useState(code);
  const [info, setInfo] = useState<PairInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setInfo(null);
    setError(null);
    setDone(false);
    if (!code) return;
    api
      .get<PairInfo>(`/api/pair/${encodeURIComponent(code)}`)
      .then(setInfo)
      .catch((e: Error) => setError(e instanceof ApiError && e.status === 404 ? e.message : `Fehler: ${e.message}`));
  }, [code]);

  function lookup(e: FormEvent) {
    e.preventDefault();
    setParams({ code: input.trim().toUpperCase() });
  }

  async function approve() {
    if (!info) return;
    setBusy(true);
    try {
      await api.post(`/api/pair/${encodeURIComponent(info.userCode)}/approve`);
      setDone(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center">
      <div className="section" style={{ maxWidth: 440 }}>
        <h1 style={{ marginBottom: 10 }}>Uploader koppeln</h1>
        {done ? (
          <>
            <p>
              Fertig. Der Uploader{info?.deviceName ? ` auf „${info.deviceName}“` : ""} ist jetzt mit deinem Konto
              verbunden und meldet sich in wenigen Sekunden.
            </p>
            <button className="btn" onClick={() => navigate("/")}>Zur Übersicht</button>
          </>
        ) : info ? (
          <>
            <p>
              Der Uploader{info.deviceName ? <> auf <b style={{ color: "var(--text)" }}>{info.deviceName}</b></> : null}{" "}
              möchte für dein Konto hochladen.
            </p>
            <div className="pair-code">{info.userCode}</div>
            <p className="warn">
              Nur koppeln, wenn genau dieser Code gerade auf deinem eigenen Bildschirm steht. Wer dir einen solchen Link
              schickt, könnte sonst in deinem Namen hochladen.
            </p>
            <button className="btn primary" disabled={busy} onClick={approve}>Koppeln</button>
          </>
        ) : (
          <>
            <p>Gib den Code ein, den der Uploader anzeigt.</p>
            <form className="inline-form" onSubmit={lookup}>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="z. B. K7Q-4MX"
                autoCapitalize="characters"
                autoComplete="off"
                aria-label="Code vom Uploader"
                maxLength={12}
              />
              <button className="btn primary" type="submit">Weiter</button>
            </form>
          </>
        )}
        {error && <p className="error" style={{ marginTop: 12 }}>{error}</p>}
      </div>
    </div>
  );
}
