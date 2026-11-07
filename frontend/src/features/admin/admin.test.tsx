import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { AdminPage } from "./AdminPage";
import { clearCsrf } from "../../lib/api-client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const adminUser = { id: "a1", username: "root", display_name: null, is_admin: true };
const memberUser = { id: "u1", username: "mia", display_name: null, is_admin: false };

function installAdmin() {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (url === "/api/v1/auth/me") return jsonResponse(200, { csrf_token: "c", user: adminUser });
    if (url === "/api/v1/access-requests" && method === "GET")
      return jsonResponse(200, [
        { id: "r1", username: "newbie", status: "pending" },
        { id: "r2", username: "old", status: "approved" },
      ]);
    if (url === "/api/v1/access-requests/r1/approve") return jsonResponse(200, { id: "r1", status: "approved" });
    if (url === "/api/v1/admin/providers")
      return jsonResponse(200, [
        { provider: "fake", reachable: true, supports_search: true, supports_fetch: true, allows_storage: true },
      ]);
    if (url === "/api/v1/admin/processing-profiles") return jsonResponse(200, []);
    if (url === "/api/v1/admin/jobs") return jsonResponse(200, { items: [], total: 0, limit: 30, offset: 0 });
    if (url === "/api/v1/admin/audit") return jsonResponse(200, []);
    throw new Error(`unexpected ${method} ${url}`);
  });
}

function renderAdmin() {
  render(
    <MemoryRouter initialEntries={["/admin"]}>
      <AuthProvider>
        <Routes>
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("admin page", () => {
  beforeEach(() => {
    clearCsrf();
    vi.unstubAllGlobals();
  });

  it("approves a pending request", async () => {
    const user = userEvent.setup();
    const fetchMock = installAdmin();
    vi.stubGlobal("fetch", fetchMock);
    renderAdmin();
    await user.click(await screen.findByRole("tab", { name: "requests" }));
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/access-requests/r1/approve",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(/approved/i);
  });

  it("shows provider status without mutating anything", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", installAdmin());
    renderAdmin();
    await user.click(await screen.findByRole("tab", { name: "providers" }));
    expect(await screen.findByText("fake")).toBeInTheDocument();
  });

  it("denies non-admin users", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/v1/auth/me") return jsonResponse(200, { csrf_token: "c", user: memberUser });
        throw new Error(`unexpected ${url}`);
      }),
    );
    renderAdmin();
    expect(await screen.findByRole("alert")).toHaveTextContent(/admins only/i);
    expect(user).toBeDefined();
  });
});
