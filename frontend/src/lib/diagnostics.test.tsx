import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { clearDiagnostics, diagnosticFetch, diagnosticReport, diagnosticRoute, recordUiError, setDiagnosticsEnabled } from "./diagnostics";
import { createIdempotencyKey } from "./idempotency";

afterEach(() => { setDiagnosticsEnabled(false); clearDiagnostics(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("keeps private data out of bounded request/error diagnostics", async () => {
  setDiagnosticsEnabled(true);
  vi.stubGlobal("fetch", vi.fn(async () => new Response('{"lyrics":"SECRET_BODY"}')));
  await diagnosticFetch("/api/v1/search/local?q=SECRET_QUERY", { method: "POST", body: "SECRET_BODY", headers: { Authorization: "SECRET_TOKEN" } });
  recordUiError("render", new TypeError("SECRET_EXCEPTION"));
  const report = JSON.stringify(diagnosticReport());
  expect(report).not.toContain("SECRET");
  expect(report).toContain("/api/v1/search/local");
  expect(report).toContain("TypeError");
  expect(diagnosticRoute("/api/v1/tracks/secret-id?token=secret")).toBe("/api/v1/tracks/:resource");
  for (let i = 0; i < 50; i++) recordUiError("javascript", new Error("never recorded"));
  expect(diagnosticReport().events).toHaveLength(40);
});

it("only records successful request timings when opted in", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response('{}')));
  await diagnosticFetch("/api/v1/providers", {});
  expect(diagnosticReport().events).toHaveLength(0);
  setDiagnosticsEnabled(true);
  await diagnosticFetch("/api/v1/providers", {});
  expect(diagnosticReport().events).toHaveLength(1);
});

it("replaces render failures with recovery and a local report, never a white screen", () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  function Broken(): never { throw new TypeError("SECRET_ERROR_CONTENT"); }
  render(<ErrorBoundary><Broken /></ErrorBoundary>);
  expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Download diagnostic report" })).toHaveAttribute("download");
  expect(JSON.stringify(diagnosticReport())).not.toContain("SECRET_ERROR_CONTENT");
  expect(diagnosticReport().events[0].kind).toBe("render");
});

it("uses random bytes without secure-context-only APIs, and tolerates missing crypto", () => {
  const first = createIdempotencyKey();
  expect(first).toMatch(/^[a-f0-9]{32}$/);
  expect(createIdempotencyKey()).not.toBe(first);
  vi.stubGlobal("crypto", undefined);
  expect(createIdempotencyKey()).toBeUndefined();
});
