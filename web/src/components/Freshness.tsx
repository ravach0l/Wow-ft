import { ago, STALE_SECONDS } from "../format";

/** Zeigt, wann der jüngste Upload kam, damit niemand alte Werte für live hält. */
export default function Freshness({ lastUpload }: { lastUpload: number | null }) {
  const stale = !lastUpload || Date.now() / 1000 - lastUpload > STALE_SECONDS;
  return (
    <div className={`freshness${stale ? " stale" : ""}`}>
      {lastUpload ? <>Jüngster Upload {ago(lastUpload)}.</> : <>Noch keine Daten hochgeladen.</>}{" "}
      Werte sind so aktuell wie der letzte Logout oder <code>/reload</code>.
    </div>
  );
}
