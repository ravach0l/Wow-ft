import { Link } from "react-router-dom";
import { ago, duration, number } from "../format";
import type { CharacterState } from "../types";
import { classColor, className, raceName } from "../wow";

export function XpBar({ c }: { c: CharacterState }) {
  const max = c.xpMax > 0 ? c.xpMax : 1;
  const xp = Math.min(100, (c.xp / max) * 100);
  const rested = Math.min(100, ((c.xp + c.rested) / max) * 100);
  return (
    <div className="bar" role="img" aria-label={`${Math.floor(xp)} % des Levels, erholt bis ${Math.floor(rested)} %`}>
      <span className="rested" style={{ width: `${rested}%` }} />
      <span className="xp" style={{ width: `${xp}%` }} />
    </div>
  );
}

export default function CharacterCard({ c, compact = false }: { c: CharacterState; compact?: boolean }) {
  const color = classColor(c.class);
  const pct = c.xpMax > 0 ? Math.floor((c.xp / c.xpMax) * 100) : 100;
  return (
    <Link to={`/c/${c.id}`} className="card">
      <div className="card-head">
        {!compact && (
          <div className="avatar" style={{ color }} aria-hidden>
            {c.photoUrl ? <img src={c.photoUrl} alt="" loading="lazy" /> : c.name.slice(0, 1)}
          </div>
        )}
        <div className="who">
          <div className="cname" style={{ color }}>{c.name}</div>
          <div className="meta">
            {raceName(c.race)} {className(c.class)}
            {!compact && c.zone ? ` · ${c.zone}` : ""}
          </div>
        </div>
        <div className="level">
          {c.level}
          <small>Level</small>
        </div>
      </div>
      <XpBar c={c} />
      <div className="row">
        <span>
          <b>{pct} %</b> · {number(c.xp)} / {number(c.xpMax)}
        </span>
        <span>{ago(c.ts)}</span>
      </div>
      {!compact && (
        <div className="row" style={{ marginTop: 4 }}>
          {!c.hidden.includes("pace") && <span>{c.xpPerHour ? `${number(c.xpPerHour)} XP/Std.` : "XP/Std. –"}</span>}
          <span>{c.behindLeader > 0 ? `${number(c.behindLeader)} XP zurück` : "vorn"}</span>
        </div>
      )}
      {!compact && c.playedTotal != null && (
        <div className="row" style={{ marginTop: 4 }}>
          <span>Spielzeit {duration(c.playedTotal)}</span>
          {c.deaths ? <span>{c.deaths} {c.deaths === 1 ? "Tod" : "Tode"}</span> : null}
        </div>
      )}
    </Link>
  );
}
