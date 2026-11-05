import { createContext, useContext } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { ApiError, loginUrl } from "./api";
import { storageGet, useApi } from "./hooks";
import CharacterPage from "./pages/CharacterPage";
import FeedPage from "./pages/FeedPage";
import InvitePage from "./pages/InvitePage";
import OverviewPage from "./pages/OverviewPage";
import ProfilePage from "./pages/ProfilePage";
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
          <Route path="/c/:charId" element={<CharacterPage />} />
          <Route path="/profil" element={<ProfilePage />} />
          <Route path="/invite/:code" element={<InvitePage />} />
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
  return (
    <header className="topbar">
      <NavLink to="/" className="brand">Freundes-Tracker</NavLink>
      <nav className="nav">
        {gid && <NavLink to={`/g/${gid}`} end>Übersicht</NavLink>}
        {gid && <NavLink to={`/g/${gid}/feed`}>Feed</NavLink>}
        <NavLink to="/profil">{me.name}</NavLink>
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
