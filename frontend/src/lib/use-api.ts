import { useCallback, useEffect, useState } from "react";
import { ApiError, get, getText } from "./api-client";

export interface UseGetResult<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  status: number | null;
  reload: () => void;
}
type Snapshot<T> = Omit<UseGetResult<T>, "reload"> & { key: string | null; nonce: number };

/** Render-time identity check prevents even one frame of another resource's data. */
function useResource<T>(path: string | null, fetcher: (path: string, signal: AbortSignal) => Promise<T>): UseGetResult<T> {
  const [nonce, setNonce] = useState(0);
  const [snapshot, setSnapshot] = useState<Snapshot<T> | null>(null);
  const reload = useCallback(() => setNonce((n) => n + 1), []);
  useEffect(() => {
    if (path === null) return;
    const controller = new AbortController();
    const base = { key: path, nonce, data: null, error: null, loading: true, status: null };
    setSnapshot(base);
    fetcher(path, controller.signal).then((data) => {
      if (!controller.signal.aborted) setSnapshot({ ...base, data, loading: false, status: 200 });
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setSnapshot({ ...base, loading: false,
        error: error instanceof Error ? error.message : "Request failed",
        status: error instanceof ApiError ? error.status : null });
    });
    return () => controller.abort();
  }, [path, nonce, fetcher]);
  if (path === null || snapshot?.key !== path || snapshot.nonce !== nonce) {
    return { data: null, error: null, loading: path !== null, status: null, reload };
  }
  return { ...snapshot, reload };
}

export function useGet<T>(path: string | null): UseGetResult<T> {
  return useResource<T>(path, get);
}

export function useText(path: string | null): UseGetResult<string> {
  return useResource(path, getText);
}
