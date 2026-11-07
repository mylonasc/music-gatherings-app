import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, post } from "../../lib/api-client";
import { useGet } from "../../lib/use-api";
import { ErrorNotice, Loading, Page } from "../../components/ui";
import { useAuth } from "../auth/AuthContext";
import { JobsPanel } from "./JobsPanel";
import { ProcessingPanel } from "./ProcessingPanel";
import { ProvidersPanel } from "./ProvidersPanel";

interface AccessRequest {
  id: string;
  username: string;
  status: string;
}

const TABS = ["requests", "providers", "processing", "jobs", "audit"] as const;

export function AdminPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<(typeof TABS)[number]>("requests");

  if (user && !user.is_admin) {
    return (
      <Page title="Administration">
        <p role="alert">Admins only. Your account does not have admin access.</p>
        <p>
          <Link to="/">Back to jam tracks</Link>
        </p>
      </Page>
    );
  }

  return (
    <Page title="Administration">
      <div role="tablist" aria-label="Administration sections">
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </div>
      {tab === "requests" && <AccessRequests />}
      {tab === "providers" && <ProvidersPanel />}
      {tab === "processing" && <ProcessingPanel />}
      {tab === "jobs" && <JobsPanel />}
      {tab === "audit" && <AuditLog />}
    </Page>
  );
}

function AccessRequests() {
  const { data, error, loading, reload } = useGet<AccessRequest[]>("/api/v1/access-requests");
  const [notice, setNotice] = useState<string | null>(null);

  async function decide(id: string, action: "approve" | "reject") {
    setNotice(null);
    try {
      await post(`/api/v1/access-requests/${id}/${action}`, {});
      setNotice(`Request ${action}d.`);
      reload();
    } catch (err: unknown) {
      setNotice(err instanceof ApiError ? err.message : "Decision failed.");
    }
  }

  if (loading) return <Loading label="Loading requests…" />;
  if (error) return <ErrorNotice message={error} onRetry={reload} />;
  const pending = (data ?? []).filter((r) => r.status === "pending");

  return (
    <section aria-label="Access requests">
      <h3>Pending access requests</h3>
      {notice && <p role="status">{notice}</p>}
      {pending.length === 0 && <p role="status">No pending requests.</p>}
      <ul>
        {pending.map((request) => (
          <li key={request.id}>
            {request.username}{" "}
            <button type="button" onClick={() => void decide(request.id, "approve")}>
              Approve
            </button>{" "}
            <button type="button" onClick={() => void decide(request.id, "reject")}>
              Reject
            </button>
          </li>
        ))}
      </ul>
      <h3>Decided</h3>
      <ul>
        {(data ?? [])
          .filter((r) => r.status !== "pending")
          .map((request) => (
            <li key={request.id}>
              {request.username} — {request.status}
            </li>
          ))}
      </ul>
    </section>
  );
}

interface AuditEntry {
  id: string;
  actor_user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string | null;
}

function AuditLog() {
  const { data, error, loading, reload } = useGet<AuditEntry[]>("/api/v1/admin/audit?limit=50");
  if (loading) return <Loading label="Loading audit trail…" />;
  if (error) return <ErrorNotice message={error} onRetry={reload} />;
  return (
    <section aria-label="Audit trail">
      <h3>Recent admin and security events</h3>
      {(data ?? []).length === 0 && <p role="status">No events yet.</p>}
      <ul>
        {(data ?? []).map((entry) => (
          <li key={entry.id}>
            {entry.created_at} — {entry.action}
            {entry.entity_type ? ` ${entry.entity_type}:${entry.entity_id}` : ""}
          </li>
        ))}
      </ul>
    </section>
  );
}
