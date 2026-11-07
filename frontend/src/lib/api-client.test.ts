import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, clearCsrf, getCsrfToken, setCsrfToken } from "./api-client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client", () => {
  beforeEach(() => {
    clearCsrf();
    vi.unstubAllGlobals();
  });

  it("sends the CSRF token on mutations but not on reads", async () => {
    const seen: Record<string, string | null>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        const headers = new Headers(init?.headers);
        seen.push({
          method: init?.method ?? "GET",
          csrf: headers.get("X-CSRF-Token"),
          credentials: (init?.credentials as string) ?? "",
        });
        return jsonResponse(200, { ok: true });
      }),
    );
    setCsrfToken("token-123");
    await api("/api/v1/crews");
    expect(seen[0].csrf).toBeNull();
    expect(seen[0].credentials).toBe("include");
    await api("/api/v1/crews", { method: "POST", body: {} });
    expect(seen[1].csrf).toBe("token-123");
  });

  it("clears the token on 401 and raises typed errors", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(401, { detail: "login required" })));
    setCsrfToken("stale");
    await expect(api("/api/v1/auth/me")).rejects.toMatchObject({ status: 401 });
    expect(getCsrfToken()).toBeNull();
  });

  it("raises ApiError with the server detail message", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(403, { detail: "admin required" })));
    const error = await api("/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("admin required");
  });
});
