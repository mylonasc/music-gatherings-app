#!/usr/bin/env node
/**
 * Seed an E2E run against the real stack (fresh Compose volume).
 *
 * Prerequisites: `docker compose exec backend python -m app.cli create-admin
 * --username <ADMIN>` with MUSIC_GATHERINGS_BOOTSTRAP_PASSWORD set, and the
 * stack reachable at API_BASE_URL (default http://localhost:8000).
 *
 * Writes tests/e2e/.seed.json (gitignored) for the specs. All credentials are
 * throwaway CI-only values, never real user secrets.
 */
import { writeFileSync } from "node:fs";

const API = process.env.API_BASE_URL ?? "http://localhost:8000";
const ADMIN_USER = process.env.SEED_ADMIN_USER ?? "root";
const ADMIN_PASS = process.env.SEED_ADMIN_PASSWORD;
const MEMBER_USER = "e2e-member";
const MEMBER_PASS = "e2e-member-pass-1";

if (!ADMIN_PASS) {
  console.error("Set SEED_ADMIN_PASSWORD to the bootstrapped admin password.");
  process.exit(1);
}

async function api(path, { method = "GET", body, cookie, csrf } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (cookie) headers.Cookie = cookie;
  if (csrf) headers["X-CSRF-Token"] = csrf;
  const response = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw new Error(`${method} ${path} -> ${response.status}: ${await response.text()}`);
  }
  const cookieOut = response.headers.get("set-cookie")?.split(";")[0] ?? cookie;
  const json = response.status === 204 ? null : await response.json();
  return { json, cookie: cookieOut };
}

const adminLogin = await api("/api/v1/auth/login", {
  method: "POST",
  body: { username: ADMIN_USER, password: ADMIN_PASS },
});
const adminCookie = adminLogin.cookie;
const adminCsrf = adminLogin.json.csrf_token;

const crews = (await api("/api/v1/crews", { cookie: adminCookie })).json;
const defaultCrew = crews[0];

// Second user joins the default crew through the public flow.
await api("/api/v1/access-requests", {
  method: "POST",
  body: { username: MEMBER_USER, password: MEMBER_PASS },
});
const pending = (await api("/api/v1/access-requests", { cookie: adminCookie })).json;
const memberRequest = pending.find((r) => r.username === MEMBER_USER);
await api(`/api/v1/access-requests/${memberRequest.id}/approve`, {
  method: "POST",
  cookie: adminCookie,
  csrf: adminCsrf,
});
const memberLogin = await api("/api/v1/auth/login", {
  method: "POST",
  body: { username: MEMBER_USER, password: MEMBER_PASS },
});
const memberCookie = memberLogin.cookie;
const memberCsrf = memberLogin.json.csrf_token;

// A second crew whose track the member must NOT see.
const otherCrew = (
  await api("/api/v1/crews", {
    method: "POST",
    cookie: adminCookie,
    csrf: adminCsrf,
    body: { name: "Hidden Crew" },
  })
).json;

async function suggest(crewId, track, cookie, csrf) {
  return (
    await api(`/api/v1/crews/${crewId}/tracks`, {
      method: "POST",
      cookie,
      csrf,
      body: track,
    })
  ).json;
}

const seeded = await suggest(
  defaultCrew.id,
  {
    title: "Blue Test Train",
    artist: "The Determinists",
    description: "Seeded track for Playwright.",
    genres: ["Test"],
    piano_suitability: "suggested",
  },
  adminCookie,
  adminCsrf,
);
await suggest(
  defaultCrew.id,
  { description: "Untitled seeded track." },
  adminCookie,
  adminCsrf,
);
const hidden = await suggest(
  otherCrew.id,
  { title: "Hidden Song", artist: "Nobody" },
  adminCookie,
  adminCsrf,
);

// Lyrics artifact on the first track (drives local search + detail views).
const version = (
  await api(`/api/v1/tracks/${seeded.track_id}/versions`, {
    method: "POST",
    cookie: adminCookie,
    csrf: adminCsrf,
    body: { label: "Seeded" },
  })
).json;
const lyrics = new Blob(["Rolling down the test track line\n"], { type: "text/plain" });
const uploadForm = new FormData();
uploadForm.set("file", lyrics, "seed-lyrics.txt");
uploadForm.set("kind", "lyrics");
const upload = await fetch(
  `${API}/api/v1/tracks/${seeded.track_id}/versions/${version.id}/artifacts/upload`,
  {
    method: "POST",
    headers: { Cookie: adminCookie, "X-CSRF-Token": adminCsrf },
    body: uploadForm,
  },
);
if (!upload.ok) throw new Error(`upload failed: ${upload.status} ${await upload.text()}`);

// The member votes on the seeded track so vote state renders for them.
await api(`/api/v1/crews/${defaultCrew.id}/tracks/${seeded.crew_track_id}/vote`, {
  method: "PUT",
  cookie: memberCookie,
  csrf: memberCsrf,
  body: { value: 1 },
});

writeFileSync(
  new URL("./.seed.json", import.meta.url),
  JSON.stringify(
    {
      users: {
        admin: { username: ADMIN_USER, password: ADMIN_PASS },
        member: { username: MEMBER_USER, password: MEMBER_PASS },
      },
      defaultCrewId: defaultCrew.id,
      trackId: seeded.track_id,
      trackTitle: "Blue Test Train",
      hiddenTrackId: hidden.track_id,
    },
    null,
    2,
  ),
);
console.log("Seeded E2E data for track", seeded.track_id);
