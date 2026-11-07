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
contracts/          Versioned service contracts (populated from S07/S09)
services/ingestion/ Provider adapters (from S07/S08)
services/processor/ Normalization/post-processing (from S09)
tests/e2e/          Playwright flows (from S12)
deploy/             Ops notes; Compose file lives at repo root
```

## CI

`ci.yml` runs backend lint/type/tests, frontend typecheck/build, `docker compose
config`, image builds, and a tracked-secrets check on every push/PR to `main`.
