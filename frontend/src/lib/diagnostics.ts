/** Local bounded diagnostics, deliberately excluding URLs, content and secrets. */
type DiagnosticEvent = {
  time: string;
  kind: "render" | "javascript" | "promise" | "request";
  route: string;
  errorType?: string;
  method?: string;
  status?: number;
  durationMs?: number;
};

let enabled = false;
let revision = 0;
const events: DiagnosticEvent[] = [];
const listeners = new Set<() => void>();
function changed() { revision++; listeners.forEach((listener) => listener()); }
export const subscribeDiagnostics = (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; };
export const diagnosticsRevision = () => revision;
export const diagnosticsEnabled = () => enabled;
export function setDiagnosticsEnabled(value: boolean) { enabled = value; changed(); }
export function clearDiagnostics() { events.length = 0; changed(); }

/** Classify routes, never retain user paths, IDs, search strings or URL queries. */
export function diagnosticRoute(path: string): string {
  const pathname = path.split(/[?#]/, 1)[0];
  if (/^\/api\/v1\/search\/(local|online)$/.test(pathname)) return pathname;
  if (/^\/api\/v1\/(auth|providers|imports|jobs|tracks|crews|artifacts|admin|access-requests)(\/|$)/.test(pathname)) {
    return `/api/v1/${pathname.split("/")[3]}/:resource`;
  }
  if (["/", "/login", "/request-access", "/search", "/crew", "/admin", "/add", "/diagnostics"].includes(pathname)) return pathname;
  if (pathname.startsWith("/tracks/")) return "/tracks/:id";
  return "/other";
}
function record(event: Omit<DiagnosticEvent, "time">) {
  events.push({ time: new Date().toISOString(), ...event });
  if (events.length > 40) events.shift();
  changed();
}
export function recordUiError(kind: "render" | "javascript" | "promise", error: unknown) {
  // Exception messages/stacks may contain lyrics, queries or credential values.
  const allowed = ["Error", "TypeError", "SyntaxError", "ReferenceError", "RangeError"];
  const errorType = error instanceof Error && allowed.includes(error.name) ? error.name : "Error";
  record({ kind, errorType, route: diagnosticRoute(window.location.pathname) });
}
export async function diagnosticFetch(path: string, options: RequestInit): Promise<Response> {
  const start = performance.now();
  const method = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"].includes(options.method ?? "GET") ? options.method ?? "GET" : "OTHER";
  try {
    const response = await fetch(path, options);
    if (enabled || !response.ok) record({ kind: "request", route: diagnosticRoute(path), method, status: response.status, durationMs: Math.round(performance.now() - start) });
    return response;
  } catch (error) {
    if (!(error instanceof DOMException && error.name === "AbortError")) record({ kind: "request", route: diagnosticRoute(path), method, status: 0, durationMs: Math.round(performance.now() - start) });
    throw error;
  }
}
export function diagnosticReport() {
  const assets = Array.from(document.scripts).map((script) => script.src.split("/").pop() ?? "").filter((name) => /^index-[a-zA-Z0-9_-]+\.js$/.test(name));
  return {
    schemaVersion: 1, capturedAt: new Date().toISOString(),
    environment: {
      secureContext: window.isSecureContext === true,
      randomUUIDAvailable: typeof globalThis.crypto?.randomUUID === "function",
      getRandomValuesAvailable: typeof globalThis.crypto?.getRandomValues === "function",
      online: navigator.onLine, userAgent: navigator.userAgent.slice(0, 200),
      viewport: { width: window.innerWidth, height: window.innerHeight }, assets,
    },
    recordingRequests: enabled, events: events.map((event) => ({ ...event })),
  };
}
export function installGlobalDiagnostics() {
  const onError = (event: ErrorEvent) => recordUiError("javascript", event.error);
  const onRejection = (event: PromiseRejectionEvent) => recordUiError("promise", event.reason);
  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onRejection);
  return () => { window.removeEventListener("error", onError); window.removeEventListener("unhandledrejection", onRejection); };
}
