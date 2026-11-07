# Operations: deployment, configuration, backup, and known limits

## Deployment

```bash
cp .env.example .env   # optional; never commit .env
docker compose up -d --build
docker compose exec -e MUSIC_GATHERINGS_BOOTSTRAP_PASSWORD='<secret>' \
  backend python -m app.cli create-admin --username <name>
```

The backend entrypoint runs `alembic upgrade head` before every start, so
upgrades are just `git pull && docker compose up -d --build`. Migrations are
forward-only: always take a backup (below) before upgrading.

Only the UI (`frontend:8080`, host `3000`) and the API (`backend:8000`) are
published. Worker, ingestion, and processor services share the private
`app-net` network and publish nothing. All containers run as unprivileged
users (`appuser`, `nginx`); the backend entrypoint briefly starts as root
only to fix volume ownership, then permanently drops privileges.

## Configuration reference

Environment variables (all optional unless noted):

| Variable | Default | Purpose |
| --- | --- | --- |
| `MUSIC_GATHERINGS_APP_ENV` | `development` | `production` enables secure cookies |
| `MUSIC_GATHERINGS_FRONTEND_PORT` | 3000 | Compose published UI host port; internal port stays 8080 |
| `MUSIC_GATHERINGS_BACKEND_PORT` | 8000 | Compose published API host port; internal port stays 8000 |
| `MUSIC_GATHERINGS_DATABASE_URL` | `sqlite:////data/database/app.sqlite3` | structured storage |
| `MUSIC_GATHERINGS_DATA_DIR` | `/data` | object-store root inside containers |
| `MUSIC_GATHERINGS_MAX_OBJECT_BYTES` | 52428800 | upload/artifact size cap |
| `MUSIC_GATHERINGS_SESSION_TTL_SECONDS` | 604800 | session lifetime (7 days) |
| `MUSIC_GATHERINGS_LOGIN_MAX_ATTEMPTS` / `_WINDOW_SECONDS` | 10 / 300 | login + access-request throttling |
| `MUSIC_GATHERINGS_ONLINE_SEARCH_PER_USER_PER_HOUR` | 30 | per-user online search quota |
| `MUSIC_GATHERINGS_ONLINE_IMPORT_PER_USER_PER_HOUR` | 20 | per-user import quota |
| `MUSIC_GATHERINGS_PROCESSOR_URL` | `http://processor:8004` | normalization service |
| `MUSIC_GATHERINGS_PROVIDER_TIMEOUT_SECONDS` | 15 | provider HTTP timeout |
| `LRCLIB_ALLOW_STORAGE` | true | personal local lyric imports; set false for reference-only behavior where rights are unknown |
| `LRCLIB_REQUESTS_PER_MINUTE` | 20 | LRCLIB overall outbound quota (search 6/min, fetch 10/min also apply) |
| `LRCLIB_MIN_INTERVAL_SECONDS` | 0.5 | minimum outbound spacing; must be between 0.2 and 60 seconds |
| `E2E_*`, `SEED_*` | unset | test-only knobs, never production |

Secrets live only in the environment (or a secrets manager mounting them as
env). They never appear in logs, job payloads, diagnostics, or Git.

## Backup and restore

**Warning:** the current restore script deletes volumes before validating the
archive, has no rollback, and assumes the default Compose project/volume name.
Do not use it on the only copy of production data. Safety work is tracked in
[#22](https://github.com/mylonasc/music-gatherings-app/issues/22); test recovery
only with isolated disposable volumes until then.

```bash
./deploy/backup.sh [backup-dir]     # stops the stack, archives the volume
./deploy/restore.sh <archive.tgz>   # destroys the volume, restores, leaves stack down
docker compose up -d                # then verify: health, login, one track read
```

The archive contains `database/app.sqlite3*` and `objects/` plus a manifest
(date, volume, git revision). Objects are immutable once written, so a
stopped-stack tarball plus the SQLite files is a coherent snapshot. The CI
`backup-restore` job is intended to exercise the full cycle on every push to
`main`; check its actual result rather than assuming recovery is verified.

## Upgrade procedure

1. `./deploy/backup.sh`
2. `git pull && docker compose up -d --build`
3. Check `backend` logs for `alembic` migration output and `/health`.
4. To roll back: `docker compose down -v`, `./deploy/restore.sh <archive>`,
   check out the previous revision, `docker compose up -d --build`.

## Resource and security posture

- Request/file caps: uploads bounded by `MAX_OBJECT_BYTES`; processor input
  capped at 1 MiB and outputs at 2 MiB; action payloads length-limited.
- Timeouts: provider calls 15 s, processor calls 60 s, job leases 300 s with
  bounded retries and backoff; worker shuts down gracefully on SIGTERM/SIGINT.
- Rate limits: login/access-request throttling, per-user online quotas,
  per-service token buckets (overall/search/fetch + spacing/concurrency),
  provider 429 cooldowns, circuit breakers, and inbound gates on provider
  services. Effective limits are observable via admin panels and `/v1/stats`.
- Uploaded bytes are never executed: rendered service HTML is escaped at
  render time; artifact downloads are `attachment` + `nosniff`; the UI only
  sanitizes inline music HTML with an inert tag/attribute allowlist, including
  processor output. Plain lyrics and LRC remain inert text.
- Passwords are Argon2id hashes; sessions are HttpOnly + SameSite cookies
  with CSRF double-submit on mutations; agent credentials are hashed
  bearer tokens scoped to one crew with audited, read-only tools.

## Known limitations (product, not bugs)

- **LRCLIB**: personal local plain/LRC lyric imports, no OAuth/key. Coverage and
  accuracy depend on community records; some tracks are instrumental or missing
  lyrics. LRC is preserved but not played in sync. API availability is not a
  blanket redistribution license; disable storage for deployments without rights.
  Genius has been retired; its existing source records remain intact.
- **Ultimate Guitar**: explicitly disabled — no public or licensed API
  exists, and scraping would violate ToS/publisher rights. The service
  returns structured 503s until a licensed API exists.
- **Notation**: reliable extraction from PDF scans is not promised;
  unsupported scans stay opaque with honest fallbacks. Chord propagation
  across repeats is conservative and warns instead of inventing notation.
- **Devices**: mobile layouts are verified with Playwright device emulation
  (Chromium + WebKit viewports, touch targets, axe checks). Emulation is not
  proof of real-device behavior: smoke-check a real phone before release
  when available and note any deviations here.
- **Scale**: one host, one replica per provider, SQLite + single worker.
  PostgreSQL/Redis/object-store migration paths are interfaces, not
  implementations, at this stage.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `invalid CSRF token` after refresh | old UI build (fixed: `/me` reissues the token) | rebuild frontend |
| Login `429 too many attempts` | throttle doing its job | wait out the window; check for brute force |
| Job stuck `queued` with `wait_reason` | provider cooldown/backoff | inspect job, wait, or cancel |
| Job `failed`: `provider_unavailable` | disabled/unsupported provider | pick another provider |
| Worker not picking up jobs | worker down or lease held | `docker compose ps/logs worker`, cancel stuck jobs |
| FTS/migration errors on start | volume from an incompatible revision | restore from backup, upgrade stepwise |
