import { Link, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { LoginPage, RequestAccessPage } from "../features/auth/AuthPages";
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

function Shell() {
  const { user, logout } = useAuth();
  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <h1>Music Gatherings</h1>
        <nav aria-label="Primary">
          <ul>
            <li>
              <Link to="/">Jam tracks</Link>
            </li>
            <li>
              <Link to="/search">Online search</Link>
            </li>
            <li>
              <Link to="/crew">Crew</Link>
            </li>
          </ul>
        </nav>
        {user && (
          <p>
            {user.username}{" "}
            <button
              type="button"
              onClick={() => {
                void logout();
              }}
            >
              Sign out
            </button>
          </p>
        )}
      </header>
      <main id="main" className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/request-access" element={<RequestAccessPage />} />
      <Route element={<Protected />}>
        <Route element={<Shell />}>
          <Route index element={<TracksPage />} />
          <Route path="tracks/:trackId" element={<TrackDetailPage />} />
          <Route path="search" element={<OnlineSearchPage />} />
          <Route path="crew" element={<CrewPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
