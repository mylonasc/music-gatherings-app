import { Link, useNavigate } from "react-router-dom";
import { ErrorNotice, Loading, Page } from "../../components/ui";
import { useGet } from "../../lib/use-api";
import { SuggestTrackForm } from "../tracks/SuggestTrackForm";
import { addMethods } from "./methods";

export function AddTrackPage() {
  const { data: crews, error, loading, reload } = useGet<{ id: string; name: string }[]>("/api/v1/crews");
  const navigate = useNavigate();
  return <Page title="Bring a song">
    <p>Every great session starts with an idea. Choose how you’d like to add yours.</p>
    <div className="method-grid">{addMethods.map((method) => <article className="track-card" key={method.id}>
      <span className="song-mark" aria-hidden="true">{method.symbol}</span><h3>{method.title}</h3><p>{method.description}</p>
      {method.to.startsWith("#") ? <a href={method.to}>Add an idea</a> : <Link to={method.to}>{method.id === "material" ? "Choose a track" : "Search providers"}</Link>}
    </article>)}</div>
    {loading && <Loading label="Loading your crew…" />}{error && <ErrorNotice message={error} onRetry={reload} />}
    {!loading && !error && !crews?.length && <p role="status">Join a crew before adding tracks.</p>}
    {crews?.[0] && <section id="manual" className="surface-panel" aria-label="Manual suggestion"><SuggestTrackForm crewId={crews[0].id} initialOpen onCreated={(item) => navigate(`/tracks/${item.track_id}`)} /></section>}
  </Page>;
}
