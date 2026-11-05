import { Link } from "react-router-dom";
import { ago } from "../format";
import type { FeedEvent } from "../types";
import { classColor } from "../wow";

export default function EventLine({ e, showName = true }: { e: FeedEvent; showName?: boolean }) {
  return (
    <li>
      <span>
        {showName && (
          <Link to={`/c/${e.character.id}`} style={{ color: classColor(e.character.class), fontWeight: 600 }}>
            {e.character.name}
          </Link>
        )}{" "}
        {e.text}
      </span>
      <span className="when" title={new Date(e.ts * 1000).toLocaleString("de-DE")}>{ago(e.ts)}</span>
    </li>
  );
}
