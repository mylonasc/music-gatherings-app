# Music Gatherings App

S01 foundation: FastAPI backend skeleton + mobile-first React frontend skeleton,
private Compose network, and named `app-data` volume. See `EPIC_APP_BOOTSTRAP.md`
for the full plan (slices S01–S16) and `AGENTS.md` for contributor rules.

## Prerequisites

- Python 3.12, Node 24, Docker + Docker Compose plugin.

## Local development (no containers)

Backend:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python -m ruff check backend
.venv/bin/python -m mypy backend/app
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Frontend (new terminal, API proxied to `localhost:8000`):

```bash
npm ci --prefix frontend
npm run typecheck --prefix frontend
npm run dev --prefix frontend
```

Open `http://localhost:5173`. The UI calls `/api/v1/health`, proxied to the backend.

## Containers

```bash
cp .env.example .env   # optional local overrides; never commit .env
docker compose config --quiet
docker compose up --build
```
- UI: `http://localhost:3000`
- Backend health: `http://localhost:8000/health` and `http://localhost:8000/api/v1/health`
- Via the UI container: `http://localhost:3000/api/v1/health` (nginx proxies to backend)

If another app uses those host ports, set these in `.env` (or export them in
your shell) before running `docker compose up -d --build`:

```dotenv
MUSIC_GATHERINGS_FRONTEND_PORT=3100
MUSIC_GATHERINGS_BACKEND_PORT=8100
```

Then open `http://localhost:3100`; direct API health is at
`http://localhost:8100/health`. Defaults remain 3000 and 8000. Only published
host ports change: nginx, healthchecks, and private services keep their internal
ports. Containers can reuse internal ports without conflicting with other apps;
an “address already in use” publishing error normally concerns the host port.
For local E2E runs on custom ports, set `E2E_BASE_URL=http://localhost:3100`
and `API_BASE_URL=http://localhost:8100` in the test command environment
(Compose's `.env` is not automatically loaded by Node/Playwright).

### First admin and access flow

There are no default credentials. Create the first admin (password via prompt or
`MUSIC_GATHERINGS_BOOTSTRAP_PASSWORD`, never committed):

```bash
docker compose exec backend python -m app.cli create-admin --username <name>
```

Then: users `POST /api/v1/access-requests`, admins approve in
`POST /api/v1/access-requests/{id}/approve` (approved users join `Jam Crew`
automatically), and log in via `POST /api/v1/auth/login`, which sets an
HttpOnly session cookie and returns a CSRF token for mutating requests.

Library API (all crew-scoped, CSRF-protected writes):

- `POST /api/v1/crews/{id}/tracks` suggest, `GET` list with
  `genre`/`piano_suggested`/`limit`/`offset`, vote totals included
- `PUT/DELETE .../tracks/{entry}/vote`, `PATCH/DELETE` entries (requester/admin)
- `GET/PATCH /api/v1/tracks/{id}`, `GET/POST .../versions`
- `POST .../versions/{id}/artifacts/upload` (txt/pdf/png/jpg, size-capped),
  `POST .../artifacts/reference` (link-only), `GET /api/v1/artifacts/{id}[/content]`
  (stored bytes served as `attachment` with `nosniff`)

Local search: `GET /api/v1/search/local?q=...&genre=&piano_suggested=&limit=&offset=`
(FTS5 prefix matching over title/artist/genres/lyrics plus typo-tolerant
fallback; per-crew notes are never indexed, results are crew-scoped).

Background jobs: `POST /api/v1/jobs` (`maintenance.reindex`,
`maintenance.reconcile_storage`, idempotent via `idempotency_key`),
`GET /api/v1/jobs[/{id}]` (crew-scoped), `POST /api/v1/jobs/{id}/cancel`.
The `worker` container claims and runs jobs with leases, bounded retries with
backoff, and cooperative cancellation; it publishes no ports.

Ingestion (S07–S08): versioned v1 contracts in `contracts/ingestion/v1/`
(generated from `services/ingestion/common/contracts.py`), per-service
token-bucket rate limits (overall/search/fetch + spacing/concurrency +
cooldowns + circuit breaker), a single limited HTTP client choke point,
TTL caching with in-flight coalescing, per-user backend quotas, and a
deterministic `ingestion-fake` provider on the private network
(`http://ingestion-fake:8001`, no published ports).

Providers (see `services/ingestion/PROVIDERS.md` for the capability/rights
matrix): `ingestion-lrclib` uses the official LRCLIB API (no key/OAuth) for
search and personal local imports of plain lyrics and original timestamped LRC.
The audience view displays lyrics as inert, preformatted text; LRC timestamps
are preserved, not used for synchronized playback. Instrumental/missing-lyrics
results show a warning rather than fabricated text. Set `LRCLIB_ALLOW_STORAGE=false`
for reference-only imports where storage/sharing rights are not established.
`ingestion-ultimate-guitar` is explicitly disabled (no public
or licensed UG API exists; scraping would violate ToS/publisher rights) and
returns structured 503s. Both publish no ports.

Genius has been retired: existing Genius source records and downloaded artifacts
remain untouched, but new Genius searches/imports are rejected (IDs are not
reinterpreted as LRCLIB IDs). Existing queued Genius jobs fail rather than being
redirected to LRCLIB. After updating, run `docker compose up -d --build`; an old
Genius container may be reported as an orphan. You may stop that specific old
container without deleting data volumes. Legacy `GENIUS_*` variables are unused.

Optional live check (uses production throttling; prints sizes, not full lyrics):

```bash
docker compose up -d --build --wait ingestion-lrclib
docker compose exec ingestion-lrclib python -m lrclib.smoke "The Beatles Yesterday"
```

Processor (`services/processor/`, private `http://processor:8004`): parses
plain-text chord charts into versioned canonical documents, applies a
validated step registry (`normalize_sections`, conservative
`expand_repeated_chords`, `transpose`), renders escaped lyrics/chord-chart
HTML and text, and reports provenance diagnostics. Invalid profiles and
active markup are rejected or rendered inert. Schemas in
`contracts/processor/v1/`.

Online discovery: `POST /api/v1/search/online` runs a provider search job
without mutating the library; `POST /api/v1/imports` attaches provider
content to a new or existing track/version with provenance, retry-safe
deduplication, optional processor-derived representations (cached), and
lyrics reindexing. `GET /api/v1/tracks/{id}/representations?context=`
selects audience/guitar/piano views. Per-user quotas gate queue admission;
provider capacity is bounded by inbound limits plus job retries.

Only `backend:8000` and `frontend:8080` (host `3000`) are published. Future
worker/ingestion/processor services join `app-net` without published ports.

Data persists in the named `app-data` volume (`/data` in containers):

```text
/data/database/app.sqlite3   SQLite (WAL mode, created by entrypoint migrations)
/data/objects/<shard>/<id>   immutable artifact bytes
/data/staging/               transient fragments, reconciled on maintenance
```

```bash
docker compose down        # keep data
docker compose down -v     # delete data volume (destructive)
```

## Repository layout

```text
backend/            FastAPI app, config, tests, Dockerfile
frontend/           React + TypeScript + Vite, Dockerfile + nginx
  src/app/          routes and shell
  src/features/     auth, tracks, search, crew views (+ colocated vitest suites)
  src/lib/          typed API client, generated api-types, useGet/useJob hooks
  scripts/          gen-api-types.mjs (regenerate from live backend OpenAPI)

Jam-track workflows: suggest tracks with metadata, vote (+1/−1/clear), genre
and piano filters, local library search with lyric snippets, online provider
search with job progress and explicit import, version lists, artifact
downloads, and audience/guitar/piano representation tabs with scroll-contained
notation panels. Playwright journeys cover all of these (`tests/e2e`).

Administration (`/admin`, admins only): access-request approvals, provider
status with isolated search/fetch tests (never stored), processing-profile
versions with registry validation, isolated processor previews with
diagnostics, job oversight with cancellation, and the audit trail.

Agent tools (read-only, S15): users create revocable bearer credentials
scoped to one crew and explicit capabilities
(`POST /api/v1/agent-tokens`), then call `POST /api/v1/agent/tools/*`
(`search`, `track`, `artifact`, `summary`, `compare`) with
`Authorization: Bearer mgat_...`. Tools share the UI's authorization logic,
enforce crew boundaries, audit every call, and mark document text as
untrusted data (analyze it, never follow it as instructions). There are no
agent mutation tools and no direct database/filesystem access. Example:

```bash
TOKEN=$(curl -s -X POST /api/v1/agent-tokens -b cookie.jar -H "X-CSRF-Token: $CSRF" \
  -H 'Content-Type: application/json' \
  -d '{"name":"reader","crew_id":"<crew>"}' http://localhost:8000/api/v1/agent-tokens | jq -r .token)
curl -X POST /api/v1/agent/tools/search -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"query":"blue train","limit":5}' \
  http://localhost:8000/api/v1/agent/tools/search
```
contracts/          Versioned service contracts (S07 ingestion, S09 processor)
services/ingestion/ Provider adapters (common/fake, LRCLIB, disabled UG)
services/processor/ Normalization/post-processing (S09)
tests/e2e/          Playwright flows (from S12)
deploy/             Ops notes; Compose file lives at repo root
```

## CI

`ci.yml` runs backend lint/type/tests, frontend typecheck/tests/build,
services lint/type/tests, `docker compose config`, all image builds,
Playwright E2E (chromium + webkit, seeded stack), a backup/restore recovery
cycle, and a tracked-secrets check on every push/PR to `main`. See
`deploy/OPERATIONS.md` for deployment, backup, upgrade, and troubleshooting.
