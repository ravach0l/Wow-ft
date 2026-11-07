import { createContext, useContext, useEffect, useRef, useState } from "react";
import { Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { ApiError, loginUrl } from "./api";
import { storageGet, useApi } from "./hooks";
import CharacterPage from "./pages/CharacterPage";
import DungeonsPage from "./pages/DungeonsPage";
import FeedPage from "./pages/FeedPage";
import InvitePage from "./pages/InvitePage";
import MaterialsPage from "./pages/MaterialsPage";
import OverviewPage from "./pages/OverviewPage";
import PairPage from "./pages/PairPage";
import ProfilePage from "./pages/ProfilePage";
import RacePage from "./pages/RacePage";
import type { Me } from "./types";

interface MeContextValue {
  me: Me;
  reloadMe: () => Promise<void>;
}

const MeContext = createContext<MeContextValue | null>(null);

export function useMe(): MeContextValue {
  const ctx = useContext(MeContext);
  if (!ctx) throw new Error("MeContext fehlt");
  return ctx;
}

export default function App() {
  const { data: me, error, reload } = useApi<Me>("/api/me");

  if (error instanceof ApiError && error.status === 401) return <Login />;
  if (error) return <div className="center"><p className="error">Server nicht erreichbar: {error.message}</p></div>;
  if (!me) return <div className="center muted">Lädt …</div>;

  return (
    <MeContext.Provider value={{ me, reloadMe: reload }}>
      <div className="shell">
        <TopBar me={me} />
        <Routes>
          <Route path="/" element={<Home me={me} />} />
          <Route path="/g/:groupId" element={<OverviewPage />} />
          <Route path="/g/:groupId/feed" element={<FeedPage />} />
          {me.features.race && <Route path="/g/:groupId/rennen" element={<RacePage />} />}
          <Route path="/g/:groupId/material" element={<MaterialsPage />} />
          <Route path="/g/:groupId/dungeons" element={<DungeonsPage />} />
          <Route path="/c/:charId" element={<CharacterPage />} />
          <Route path="/profil" element={<ProfilePage />} />
          <Route path="/invite/:code" element={<InvitePage />} />
          <Route path="/koppeln" element={<PairPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </MeContext.Provider>
  );
}

function currentGroupId(me: Me): number | null {
  const stored = Number(storageGet("wowft.group"));
  if (me.groups.some((g) => g.id === stored)) return stored;
  return me.groups[0]?.id ?? null;
}

function Home({ me }: { me: Me }) {
  const gid = currentGroupId(me);
  if (gid) return <Navigate to={`/g/${gid}`} replace />;
  return <Navigate to="/profil" replace />;
}

function TopBar({ me }: { me: Me }) {
  const gid = currentGroupId(me);
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  // Menü schließen bei Seitenwechsel und bei Klick daneben.
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!moreRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [open]);

  // Auf dem Handy stehen diese unter „Mehr“, am PC direkt in der Leiste.
  const secondary = gid
    ? [
        ...(me.features.race ? [{ to: `/g/${gid}/rennen`, label: "Rennen" }] : []),
        { to: `/g/${gid}/material`, label: "Material" },
        { to: `/g/${gid}/feed`, label: "Feed" },
      ]
    : [];
  const moreActive = secondary.some((l) => pathname.startsWith(l.to));

  return (
    <header className="topbar">
      <NavLink to="/" className="brand">Freundes-Tracker</NavLink>
      <nav className="nav" aria-label="Hauptmenü">
        {gid && <NavLink to={`/g/${gid}`} end>Übersicht</NavLink>}
        {gid && <NavLink to={`/g/${gid}/dungeons`}>Dungeons</NavLink>}
        {secondary.map((l) => (
          <NavLink key={l.to} to={l.to} className="secondary">{l.label}</NavLink>
        ))}
        {secondary.length > 0 && (
          <div className="more" ref={moreRef}>
            <button
              type="button"
              className={moreActive ? "active" : undefined}
              aria-expanded={open}
              aria-haspopup="menu"
              onClick={() => setOpen((v) => !v)}
            >
              Mehr ▾
            </button>
            {open && (
              <div className="more-menu" role="menu">
                {secondary.map((l) => (
                  <NavLink key={l.to} to={l.to} role="menuitem">{l.label}</NavLink>
                ))}
              </div>
            )}
          </div>
        )}
        <NavLink to="/profil" className="me" aria-label={`Profil von ${me.name}`} title={me.name}>
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <circle cx="12" cy="8" r="4" fill="currentColor" />
            <path d="M4 20c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5" fill="currentColor" />
          </svg>
          <span className="me-name">{me.name}</span>
        </NavLink>
      </nav>
    </header>
  );
}

function Login() {
  return (
    <div className="center">
      <div className="section">
        <h1 style={{ marginBottom: 10 }}>Freundes-Tracker</h1>
        <p>Level, XP und Spielzeit deiner WoW-Forever-Runde auf einen Blick.</p>
        <a className="btn primary" href={loginUrl()}>Mit Authentik anmelden</a>
      </div>
    </div>
  );
}
