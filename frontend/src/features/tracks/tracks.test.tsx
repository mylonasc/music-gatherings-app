import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { TracksPage } from "./TracksPage";
import { TrackDetailPage } from "./TrackDetailPage";
import { clearCsrf } from "../../lib/api-client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const demoUser = { id: "u1", username: "mia", display_name: null, is_admin: false };

function tracksFixture() {
  return {
    items: [
      {
        crew_track_id: "ct1",
        track_id: "t1",
        title: "Blue Test Train",
        artist: "The Determinists",
        genres: ["Test"],
        requester: "mia",
        piano_suitability: "suggested",
        vote_score: 3,
        my_vote: 1,
        version_count: 1,
        artifact_kinds: ["lyrics", "chord_chart"],
      },
      {
        crew_track_id: "ct2",
        track_id: "t2",
        title: null,
        artist: null,
        genres: [],
        requester: null,
        piano_suitability: "unknown",
        vote_score: 0,
        my_vote: null,
        version_count: 0,
        artifact_kinds: [],
      },
    ],
    total: 2,
    limit: 50,
    offset: 0,
  };
}

function installFetch(handler: (url: string) => Response | Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => handler(url)));
}

function renderTracks(handler: (url: string) => Response | Promise<Response>) {
  installFetch(handler);
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<TracksPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("jam tracks page", () => {
  beforeEach(() => {
    clearCsrf();
    vi.unstubAllGlobals();
  });

  it("renders the crew track list with metadata", async () => {
    renderTracks((url) => {
      if (url === "/api/v1/auth/me") return jsonResponse(200, demoUser);
      if (url === "/api/v1/crews") return jsonResponse(200, [{ id: "c1", name: "Jam Crew" }]);
      if (url.startsWith("/api/v1/crews/c1/tracks")) return jsonResponse(200, tracksFixture());
      throw new Error(`unexpected ${url}`);
    });
    expect(await screen.findByText("Blue Test Train — The Determinists")).toBeInTheDocument();
    expect(screen.getByText("Untitled track")).toBeInTheDocument();
    expect(screen.getByText("Votes 3")).toBeInTheDocument();
    const plusOnes = screen.getAllByRole("button", { name: "+1" });
    expect(plusOnes[0]).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(/piano-friendly/)).toBeInTheDocument();
  });

  it("shows an empty state when the crew has no tracks", async () => {
    renderTracks((url) => {
      if (url === "/api/v1/auth/me") return jsonResponse(200, demoUser);
      if (url === "/api/v1/crews") return jsonResponse(200, [{ id: "c1", name: "Jam Crew" }]);
      return jsonResponse(200, { items: [], total: 0, limit: 50, offset: 0 });
    });
    expect(await screen.findByText(/no tracks yet/i)).toBeInTheDocument();
  });

  it("shows errors with a retry action", async () => {
    let attempts = 0;
    installFetch((url) => {
      if (url === "/api/v1/auth/me") return jsonResponse(200, demoUser);
      if (url === "/api/v1/crews") return jsonResponse(200, [{ id: "c1", name: "Jam Crew" }]);
      attempts += 1;
      if (attempts === 1) return jsonResponse(500, { detail: "boom" });
      return jsonResponse(200, tracksFixture());
    });
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<TracksPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });
});

describe("track detail page", () => {
  beforeEach(() => {
    clearCsrf();
    vi.unstubAllGlobals();
  });

  it("renders versions with artifact links", async () => {
    installFetch((url) => {
      if (url === "/api/v1/auth/me") return jsonResponse(200, demoUser);
      if (url === "/api/v1/tracks/t1")
        return jsonResponse(200, {
          id: "t1",
          title: "Blue Test Train",
          artist: "The Determinists",
          description: null,
          genres: ["Test"],
          versions: [
            {
              id: "v1",
              track_id: "t1",
              label: "Studio",
              musical_key: "C",
              language: null,
              tuning: null,
              capo: null,
              notes: null,
              artifacts: [
                {
                  id: "a1",
                  track_version_id: "v1",
                  kind: "lyrics",
                  mime_type: "text/plain",
                  byte_size: 10,
                  sha256: null,
                  is_external: false,
                  external_url: null,
                  file_name: "lyrics.txt",
                  language: null,
                },
              ],
            },
          ],
          crew_entries: [],
        });
      throw new Error(`unexpected ${url}`);
    });
    render(
      <MemoryRouter initialEntries={["/tracks/t1"]}>
        <AuthProvider>
          <Routes>
            <Route path="/tracks/:trackId" element={<TrackDetailPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "Studio" })).toBeInTheDocument();
    expect(screen.getByText(/Key: C/)).toBeInTheDocument();
    const download = screen.getByRole("link", { name: /download lyrics\.txt/ });
    expect(download.getAttribute("href")).toBe("/api/v1/artifacts/a1/content");
  });
});
