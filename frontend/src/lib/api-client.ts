/**
 * Typed API client: same-origin fetch with session cookies and CSRF handling.
 *
 * The session cookie is HttpOnly (unreadable from JS); the CSRF token from
 * login lives in module memory and is sent on every mutating request. A 401
 * clears the in-memory token so stale sessions fail closed.
 */

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

export function clearCsrf(): void {
  csrfToken = null;
}

interface ApiOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {};
  let payload: string | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(options.body);
  }
  if (csrfToken && method !== "GET" && method !== "HEAD") {
    headers["X-CSRF-Token"] = csrfToken;
  }
  const response = await fetch(path, {
    method,
    headers,
    body: payload,
    signal: options.signal,
    credentials: "include",
  });
  if (response.status === 204) {
    return undefined as T;
  }
  if (response.status === 401) {
    setCsrfToken(null);
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const problem = (await response.json()) as { detail?: unknown };
      if (typeof problem.detail === "string") message = problem.detail;
    } catch {
      /* keep generic message */
    }
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
}

export const get = <T>(path: string, signal?: AbortSignal): Promise<T> =>
  api<T>(path, { signal });

export async function getText(path: string, signal?: AbortSignal): Promise<string> {
  const response = await fetch(path, { credentials: "include", signal });
  if (response.status === 401) {
    setCsrfToken(null);
  }
  if (!response.ok) {
    throw new ApiError(response.status, `Request failed (${response.status})`);
  }
  return response.text();
}

export const post = <T>(path: string, body?: unknown): Promise<T> =>
  api<T>(path, { method: "POST", body });

export const put = <T>(path: string, body?: unknown): Promise<T> =>
  api<T>(path, { method: "PUT", body });

export const patch = <T>(path: string, body?: unknown): Promise<T> =>
  api<T>(path, { method: "PATCH", body });

export const del = (path: string): Promise<void> => api<void>(path, { method: "DELETE" });
