import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, clearCsrf, get, post, setCsrfToken } from "../../lib/api-client";
import type { LoginResponse, UserOut } from "../../lib/api-types";

interface AuthContextValue {
  user: UserOut | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  requestAccess: (username: string, password: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    get<LoginResponse>("/api/v1/auth/me", controller.signal)
      .then((response) => {
        setCsrfToken(response.csrf_token);
        setUser(response.user);
      })
      .catch((err: unknown) => {
        if (!(err instanceof DOMException)) setUser(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const response = await post<LoginResponse>("/api/v1/auth/login", { username, password });
    setCsrfToken(response.csrf_token);
    setUser(response.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await post("/api/v1/auth/logout");
    } catch (err: unknown) {
      if (!(err instanceof ApiError)) throw err;
    } finally {
      clearCsrf();
      setUser(null);
    }
  }, []);

  const requestAccess = useCallback(async (username: string, password: string) => {
    await post("/api/v1/access-requests", { username, password });
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, logout, requestAccess }),
    [user, loading, login, logout, requestAccess],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
