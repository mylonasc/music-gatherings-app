import { ErrorNotice, Loading, Page } from "../../components/ui";
import { useGet } from "../../lib/use-api";
import type { MemberOut } from "../../lib/api-types";

interface Crew {
  id: string;
  name: string;
}

export function CrewPage() {
  const { data: crews, error: crewsError, loading: crewsLoading } = useGet<Crew[]>("/api/v1/crews");
  const crewId = crews && crews.length > 0 ? crews[0].id : null;
  const {
    data: members,
    error: membersError,
    loading: membersLoading,
  } = useGet<MemberOut[]>(crewId ? `/api/v1/crews/${crewId}/members` : null);

  return (
    <Page title="Jam crew">
      {crewsLoading && <Loading label="Loading crews…" />}
      {crewsError && <ErrorNotice message={crewsError} />}
      {crews?.map((crew) => (
        <section key={crew.id} aria-label={crew.name}>
          <h3>{crew.name}</h3>
        </section>
      ))}
      {membersLoading && <Loading label="Loading members…" />}
      {membersError && <ErrorNotice message={membersError} />}
      {members && (
        <>
          <h3>Members</h3>
          <ul>
            {members.map((member) => (
              <li key={member.user_id}>
                {member.username} · {member.role}
              </li>
            ))}
          </ul>
        </>
      )}
    </Page>
  );
}
