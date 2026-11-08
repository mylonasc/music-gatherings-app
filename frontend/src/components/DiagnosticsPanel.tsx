import { useSyncExternalStore } from "react";
import { clearDiagnostics, diagnosticReport, diagnosticsEnabled, diagnosticsRevision, setDiagnosticsEnabled, subscribeDiagnostics } from "../lib/diagnostics";

export function DiagnosticsPanel() {
  useSyncExternalStore(subscribeDiagnostics, diagnosticsRevision);
  const report = JSON.stringify(diagnosticReport(), null, 2);
  return <section className="surface-panel" aria-label="Local diagnostics">
    <h2>Diagnostics</h2>
    <p>This report stays in memory in this tab. Nothing is uploaded automatically. It excludes search words, song content, resource IDs, passwords, cookies and request bodies.</p>
    <p>Errors are recorded automatically. Enable request timings, reproduce the problem, then return here and download the report before reloading. Reloading clears the report and disables recording.</p>
    <label><input type="checkbox" checked={diagnosticsEnabled()} onChange={(e) => setDiagnosticsEnabled(e.target.checked)} />Record request timings for this tab</label>
    <div className="form-actions"><a className="action-link" download="music-gatherings-diagnostics.json" href={`data:application/json;charset=utf-8,${encodeURIComponent(report)}`}>Download diagnostic report</a>
      <button type="button" onClick={clearDiagnostics}>Clear report</button></div>
    <details><summary>Inspect report before sharing</summary><pre className="doc-panel" tabIndex={0} role="region" aria-label="Diagnostic report">{report}</pre></details>
  </section>;
}
