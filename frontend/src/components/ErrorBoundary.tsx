import { Component } from "react";
import type { ReactNode } from "react";
import { recordUiError } from "../lib/diagnostics";
import { DiagnosticsPanel } from "./DiagnosticsPanel";

/** Last-resort recovery; route boundaries keep the normal navigation mounted. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error) { recordUiError("render", error); }
  render() {
    if (!this.state.failed) return this.props.children;
    return <section className="surface-panel" aria-label="Application recovery">
      <h1>Something went wrong</h1>
      <p role="alert">This view could not load. You can save a diagnostic report below, then reload or return to your tracks.</p>
      <div className="form-actions"><button type="button" onClick={() => window.location.reload()}>Reload app</button><a className="action-link" href="/">Back to jam tracks</a></div>
      <DiagnosticsPanel />
    </section>;
  }
}
