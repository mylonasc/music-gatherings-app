import { Outlet } from "react-router-dom";
import "./auth.css";

export function AuthLayout() {
  return <main className="auth-layout"><aside className="auth-story" aria-label="Music Gatherings">
    <span className="brand-mark" aria-hidden="true">♫</span><p className="eyebrow">Music Gatherings</p>
    <h1>Make room<br />for a good song.</h1><p>Your crew. Your favourites.<br />Everything you need for the next jam.</p>
    <div className="staff-decoration" aria-hidden="true">♪ &nbsp; ♫ &nbsp; ♪</div>
  </aside><div className="auth-form"><Outlet /></div></main>;
}
