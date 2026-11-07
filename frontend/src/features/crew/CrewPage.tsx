import { useState } from "react";
import { Badge, EmptyState, ErrorNotice, Field, Loading, Page } from "../../components/ui";
import { useGet } from "../../lib/use-api";
import type { MemberOut } from "../../lib/api-types";

interface Crew {
  id: string;
  name: string;
}

export function CrewPage() {
  const { data: crews, error: crewsError, loading: crewsLoading } = useGet<Crew[]>("/api/v1/crews");
  const [selectedCrew, setSelectedCrew] = useState("");
  const crewId = crews?.some((c) => c.id === selectedCrew) ? selectedCrew : crews?.[0]?.id ?? null;
  const {
    data: members,
    error: membersError,
    loading: membersLoading,
  } = useGet<MemberOut[]>(crewId ? `/api/v1/crews/${crewId}/members` : null);

  return (
    <Page title="Jam crew">
      <p>Good music starts with good company. Meet the people sharing your next session.</p>
      {crewsLoading && <Loading label="Loading crews…" />}
      {crewsError && <ErrorNotice message={crewsError} />}
      {crews && !crews.length && <EmptyState title="No crew yet">Ask an administrator to approve your access.</EmptyState>}
      {!!crews?.length && <Field id="crew-choice" label="Crew"><select id="crew-choice" value={crewId ?? ""} onChange={(e) => setSelectedCrew(e.target.value)}>{crews.map((crew) => <option key={crew.id} value={crew.id}>{crew.name}</option>)}</select></Field>}
      {membersLoading && <Loading label="Loading members…" />}
      {membersError && <ErrorNotice message={membersError} />}
      {members && (
        <>
          <h3>Members</h3>
          <ul className="track-list">
            {members.map((member) => (
              <li key={member.user_id} className="track-card member-card">
                <span className="avatar" aria-hidden="true">{member.username.slice(0, 1).toUpperCase()}</span><strong>{member.username}</strong><Badge>{member.role}</Badge>
              </li>
            ))}
          </ul>
        </>
      )}
    </Page>
  );
}
