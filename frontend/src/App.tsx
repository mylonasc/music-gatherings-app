import { useEffect, useState } from "react";
import { fetchHealth, type HealthResponse } from "./api";
import "./App.css";

type HealthState =
  | { kind: "loading" }
  | { kind: "ready"; health: HealthResponse }
  | { kind: "error"; message: string };

export default function App() {
  const [state, setState] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((health) => setState({ kind: "ready", health }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState({
          kind: "error",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      });
    return () => controller.abort();
  }, []);

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <h1>Music Gatherings</h1>
        <p>Jam tracks start here. Mobile-first skeleton.</p>
      </header>
      <main id="main" className="app-main">
        <section aria-labelledby="backend-status-heading" aria-live="polite">
          <h2 id="backend-status-heading">Backend status</h2>
          {state.kind === "loading" && <p>Checking API health…</p>}
          {state.kind === "ready" && (
            <p>
              API <strong>{state.health.status}</strong> · {state.health.service} v
              {state.health.version} ({state.health.env})
            </p>
          )}
          {state.kind === "error" && (
            <p role="alert">
              Backend unreachable ({state.message}). Start the API on port 8000.
            </p>
          )}
        </section>
        <section aria-labelledby="next-heading">
          <h2 id="next-heading">What comes next</h2>
          <ul>
            <li>Jam track list as the default view</li>
            <li>Track search with local and online sources</li>
            <li>Crew and administration panels</li>
          </ul>
        </section>
      </main>
    </div>
  );
}
