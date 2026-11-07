import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./AuthContext";
import { LoginPage, RequestAccessPage } from "./AuthPages";
import { clearCsrf } from "../../lib/api-client";

function mockFetch(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  return vi.fn(async (url: string, init?: RequestInit) => handler(url, init));
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const demoUser = { id: "u1", username: "mia", display_name: null, is_admin: false };

describe("login page", () => {
  beforeEach(() => {
    clearCsrf();
    vi.unstubAllGlobals();
  });

  it("signs in and lands on the jam tracks route", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch((url) => {
      if (url === "/api/v1/auth/me") return jsonResponse(401, { detail: "login required" });
      if (url === "/api/v1/auth/login")
        return jsonResponse(200, { csrf_token: "csrf-1", user: demoUser });
      if (url === "/api/v1/crews") return jsonResponse(200, []);
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<p>jam tracks home</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await user.type(await screen.findByLabelText("Username"), "mia");
    await user.type(await screen.findByLabelText("Password"), "s3cret-long");
    await user.click(await screen.findByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.getByText("jam tracks home")).toBeInTheDocument());
    const loginCall = fetchMock.mock.calls.find(([url]) => url === "/api/v1/auth/login");
    expect(JSON.parse((loginCall?.[1]?.body as string) ?? "{}")).toEqual({
      username: "mia",
      password: "s3cret-long",
    });
  });

  it("shows server errors and validates empty input", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      mockFetch((url) => {
        if (url === "/api/v1/auth/me") return jsonResponse(401, { detail: "login required" });
        return jsonResponse(401, { detail: "invalid credentials" });
      }),
    );
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/username and password/i);

    await user.type(await screen.findByLabelText("Username"), "mia");
    await user.type(await screen.findByLabelText("Password"), "wrong");
    await user.click(await screen.findByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid credentials");
  });

  it("requests access and confirms", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch((url) => {
      if (url === "/api/v1/auth/me") return jsonResponse(401, { detail: "login required" });
      if (url === "/api/v1/access-requests") return jsonResponse(201, { id: "r1" });
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter initialEntries={["/request-access"]}>
        <AuthProvider>
          <Routes>
            <Route path="/request-access" element={<RequestAccessPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    await user.type(await screen.findByLabelText("Username"), "newbie");
    await user.type(await screen.findByLabelText(/8\+ characters/), "s3cret-long");
    await user.click(await screen.findByRole("button", { name: "Request access" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/review your request/i);
  });
});
