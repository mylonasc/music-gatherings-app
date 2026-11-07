import { useCallback, useEffect, useState } from "react";
import { ApiError, get } from "./api-client";

export interface UseGetResult<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  status: number | null;
  reload: () => void;
}

/** Consistent server-state convention: loading/error/data + manual reload. */
export function useGet<T>(path: string | null): UseGetResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (path === null) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setStatus(null);
    get<T>(path, controller.signal)
      .then((value) => {
        setData(value);
        setStatus(200);
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (err instanceof ApiError) {
          setStatus(err.status);
          setError(err.message);
        } else {
          setError(err instanceof Error ? err.message : "Request failed");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, nonce]);

  return { data, error, loading, status, reload };
}
