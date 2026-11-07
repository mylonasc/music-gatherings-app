import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./AppShell";
import { AddTrackPage } from "../features/adding/AddTrackPage";
import { AuthLayout } from "../features/auth/AuthLayout";
import { useAuth } from "../features/auth/AuthContext";
import { LoginPage, RequestAccessPage } from "../features/auth/AuthPages";
import { AdminPage } from "../features/admin/AdminPage";
import { CrewPage } from "../features/crew/CrewPage";
import { OnlineSearchPage } from "../features/search/OnlineSearchPage";
import { TrackDetailPage } from "../features/tracks/TrackDetailPage";
import { TracksPage } from "../features/tracks/TracksPage";

function Protected() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p role="status">Loading…</p>;
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <Outlet />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/request-access" element={<RequestAccessPage />} />
      </Route>
      <Route element={<Protected />}>
        <Route element={<AppShell />}>
          <Route index element={<TracksPage />} />
          <Route path="tracks/:trackId" element={<TrackDetailPage />} />
          <Route path="search" element={<OnlineSearchPage />} />
          <Route path="add" element={<AddTrackPage />} />
          <Route path="crew" element={<CrewPage />} />
          <Route path="admin" element={<AdminPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
