import { useParams } from "react-router-dom";
import EventLine from "../components/EventLine";
import { useApi } from "../hooks";
import type { FeedEvent } from "../types";

export default function FeedPage() {
  const { groupId } = useParams();
  const { data, error } = useApi<FeedEvent[]>(`/api/groups/${groupId}/feed`);
  if (error) return <p className="error">{error.message}</p>;
  if (!data) return <p className="muted">Lädt …</p>;
  return (
    <div className="section">
      <h2>Aktivität</h2>
      {data.length === 0 ? (
        <p>Noch keine Ereignisse.</p>
      ) : (
        <ul className="list">
          {data.map((e) => (
            <EventLine key={e.id} e={e} />
          ))}
        </ul>
      )}
    </div>
  );
}
