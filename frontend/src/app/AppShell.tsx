import { useEffect, useRef } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import "./shell.css";

const destinations = [
  { to: "/", label: "Jam tracks", symbol: "♫", end: true },
  { to: "/search", label: "Online search", symbol: "⌕", end: false },
  { to: "/crew", label: "Crew", symbol: "◎", end: false },
  { to: "/admin", label: "Admin", symbol: "⚙", end: false, admin: true },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const activeDestination = pathname === "/add" || pathname.startsWith("/tracks/") ? "/" : pathname;
  const main = useRef<HTMLElement>(null);
  const previousPath = useRef(pathname);
  useEffect(() => {
    if (previousPath.current !== pathname) {
      main.current?.focus();
      window.scrollTo(0, 0);
      previousPath.current = pathname;
    }
  }, [pathname]);
  return <div className="app studio-shell">
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="app-header studio-header">
      <div className="brand"><span className="brand-mark" aria-hidden="true">♫</span>
        <div><h1>Music Gatherings</h1><p>Good songs. Great company.</p></div>
      </div>
      <nav aria-label="Primary" className="primary-nav"><ul>
        {destinations.filter((item) => !item.admin || user?.is_admin).map((item) =>
          <li key={item.to}><Link to={item.to} aria-current={activeDestination === item.to ? "page" : undefined}>
            <span className="nav-symbol" aria-hidden="true">{item.symbol}</span><span>{item.label}</span>
          </Link></li>)}
      </ul></nav>
      {user && <div className="account-area"><span className="avatar" aria-hidden="true">{user.username.slice(0, 1).toUpperCase()}</span>
        <span className="account-name">{user.username}</span><button type="button" onClick={() => void logout()}>Sign out</button>
      </div>}
      <p className="sidebar-note">A little less searching.<br />A little more playing.</p>
    </header>
    <main id="main" className="app-main" tabIndex={-1} ref={main}><Outlet /></main>
  </div>;
}
