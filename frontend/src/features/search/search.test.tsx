import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { OnlineSearchPage } from "./OnlineSearchPage";
import { clearCsrf } from "../../lib/api-client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const demoUser = { id: "u1", username: "mia", display_name: null, is_admin: false };

function installSearchFetch() {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url === "/api/v1/auth/me") return jsonResponse(200, demoUser);
      if (url === "/api/v1/crews") return jsonResponse(200, [{ id: "c1", name: "Jam Crew" }]);
      if (url === "/api/v1/search/online")
        return jsonResponse(202, { id: "job-s1", kind: "online.search", status: "queued", progress: 0 });
      if (url === "/api/v1/jobs/job-s1")
        return jsonResponse(200, {
          id: "job-s1",
          kind: "online.search",
          status: "succeeded",
          progress: 1,
          result: {
            results: {
              fake: [
                {
                  provider: "fake",
                  external_id: "fake-song-1",
                  title: "Blue Test Train",
                  artist: "The Determinists",
                  artifact_types: ["lyrics"],
                  source_url: "https://example.local/x",
                  attribution: "Fake",
                },
              ],
            },
          },
        });
      if (url === "/api/v1/imports")
        return jsonResponse(202, { id: "job-i1", kind: "online.import", status: "queued", progress: 0 });
      if (url === "/api/v1/jobs/job-i1")
        return jsonResponse(200, {
          id: "job-i1",
          kind: "online.import",
          status: "succeeded",
          progress: 1,
          result: { track_id: "t9", reused: false },
        });
      throw new Error(`unexpected ${init?.method} ${url}`);
    }),
  );
  return calls;
}

describe("online search page", () => {
  beforeEach(() => {
    clearCsrf();
    vi.unstubAllGlobals();
  });

  it("searches providers and imports a hit", async () => {
    const user = userEvent.setup();
    installSearchFetch();
    render(
      <MemoryRouter initialEntries={["/search"]}>
        <AuthProvider>
          <Routes>
            <Route path="/search" element={<OnlineSearchPage />} />
            <Route path="/tracks/:trackId" element={<p>track detail</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    await user.type(await screen.findByLabelText("Song or artist"), "blue train");
    expect(screen.getByLabelText("LRCLIB")).toBeInTheDocument();
    expect(screen.queryByLabelText(/genius/i)).not.toBeInTheDocument();
    const searchButton = await screen.findByRole("button", { name: "Search online" });
    await waitFor(() => expect(searchButton).toBeEnabled());
    await user.click(searchButton);
    expect(await screen.findByText(/Blue Test Train/, { selector: "strong" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Import “Blue Test Train”/ }));
    await waitFor(() => expect(screen.getByRole("link", { name: "Open the track" })).toBeInTheDocument());
  });

  it("surfaces provider failures without mutating anything", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/v1/auth/me") return jsonResponse(200, demoUser);
        if (url === "/api/v1/crews") return jsonResponse(200, [{ id: "c1", name: "Jam Crew" }]);
        if (url === "/api/v1/search/online")
          return jsonResponse(202, { id: "job-bad", kind: "online.search", status: "queued", progress: 0 });
        return jsonResponse(200, {
          id: "job-bad",
          kind: "online.search",
          status: "failed",
          progress: 0,
          error: "provider unavailable",
        });
      }),
    );
    render(
      <MemoryRouter initialEntries={["/search"]}>
        <AuthProvider>
          <Routes>
            <Route path="/search" element={<OnlineSearchPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    await user.type(await screen.findByLabelText("Song or artist"), "blue");
    const searchButton = await screen.findByRole("button", { name: "Search online" });
    await waitFor(() => expect(searchButton).toBeEnabled());
    await user.click(searchButton);
    expect(await screen.findByRole("alert")).toHaveTextContent(/provider unavailable/);
  });
});
