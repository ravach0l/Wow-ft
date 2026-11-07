import { Link } from "react-router-dom";
import type { CharacterState } from "../types";
import { groupByZone } from "../where";
import { classColor } from "../wow";

/** Kompakte Liste „Zone: Charaktere“; Zonen mit mehreren Personen hervorgehoben. */
export default function WhereIsWho({ chars }: { chars: CharacterState[] }) {
  const zones = groupByZone(chars);
  if (zones.length === 0) return null;
  return (
    <div className="section where">
      <h2>Wer ist wo</h2>
      <ul className="list compact">
        {zones.map((z) => (
          <li key={z.zone} className={z.people > 1 ? "together" : undefined}>
            <span className="zone">{z.zone}</span>
            <span className="chips">
              {z.chars.map((c) => (
                <Link key={c.id} to={`/c/${c.id}`} className="chip" title={`${c.name} (${c.ownerName})`}>
                  <span style={{ color: classColor(c.class) }}>{c.name}</span> <b>{c.level}</b>
                </Link>
              ))}
            </span>
          </li>
        ))}
      </ul>
      <p className="muted" style={{ margin: "8px 0 0", fontSize: ".85rem" }}>
        Letzte bekannte Zone, ohne Zeitangabe. Wer seinen Aufenthaltsort nicht teilt, fehlt hier.
      </p>
    </div>
  );
}
