# Provider integrations: capability and rights matrix

Checked 2026-11-07 via web research (package registries, official docs, ToS).

## LRCLIB (`services/ingestion/lrclib/`), replacing Genius

- Official documentation: https://lrclib.net/docs.txt. Direct HTTP via the pinned
  shared `httpx` client; no third-party scraper or provider SDK dependency.
- Anonymous access is explicitly supported; no API key/OAuth required. We send
  an identifying application/version/project `User-Agent` on every request.
- Only stable read endpoints: `GET https://lrclib.net/api/search?q=...` and
  `GET https://lrclib.net/api/get/{id}`. Search returns at most 20 records with
  no pagination. No publishing, challenges, scraping, or beta API dependency.
- Capabilities: lyrics only. Fetch retains `plainLyrics` as UTF-8 `text/plain`
  and `syncedLyrics` separately as `application/x-lrc` (timestamps unchanged).
  No invented chords/sheet music, YAML parsing, or synchronized playback.
- Instrumentals and missing lyrics have explicit warnings and reference fallback.
  Search results contain metadata/availability only, never lyric bodies.
- This application's requested use is a private personal local library, with
  local imports enabled (`LRCLIB_ALLOW_STORAGE=true`). LRCLIB documents open API
  access, **not** a blanket license to redistribute every lyric. Rights remain
  with their owners; before broader/shared/public deployment establish applicable
  rights or set `LRCLIB_ALLOW_STORAGE=false` for reference-only behavior. This
  switch does not delete previously imported material.
- Both formats retain LRCLIB attribution and stable source record URL/ID. Raw
  lyrics are not interpreted as HTML. Original Genius records are not rewritten.
- Conservative defaults: overall 20/min, search 6/min, fetch 10/min, burst 1,
  concurrency 1, minimum 500ms between starts, 10s queue budget, two HTTP attempts,
  bounded 2MB decoded responses, 32-entry/5-minute result cache. Configure overall
  quota and spacing with `LRCLIB_REQUESTS_PER_MINUTE` and
  `LRCLIB_MIN_INTERVAL_SECONDS` (minimum 0.2s). These are local settings, not
  guaranteed upstream allowances. Honor provider cooldowns/Retry-After; all
  attempts, including admin tests, use the same outbound limiter.
- Legacy Genius credentials are no longer read. No database migration is needed;
  new `genius` requests fail validation rather than remapping old IDs to LRCLIB.

## Ultimate Guitar (`services/ingestion/ultimateguitar/`)

- There is **no public API** (confirmed by UG staff on their forum: publisher
  deals fund tabs via ads/subscriptions; scrapers "have all been shut down
  by ultimate-guitar"). No free or paid self-serve programmatic access exists.
- Scraping `tabs.ultimate-guitar.com` would violate their ToS and the
  publisher rights behind the content, so the adapter is **explicitly
  disabled**: capabilities report `supports_search: false` /
  `supports_fetch: false`, and both operations return structured 503
  `provider_unavailable` errors explaining the limitation.
- This is a documented product limitation, not a silent fake: the service
  implements the v1 contract (health/capabilities/error envelope) so
  orchestration (S10) and admin panels (S14) handle it uniformly. If UG ever
  offers a licensed API, this service is the integration point.

## Fake (`services/ingestion/fake/`)

- Deterministic in-memory fixtures with original placeholder text
  (public-domain-safe). `allows_storage: true` so S10 import flows and S12
  Playwright suites can exercise storage without any upstream dependency.
- Must never be mistaken for a real provider: service name, provider id
  (`fake`), and attribution strings all say so.

## Rules for every adapter (enforced in review, not just docs)

1. Every outbound HTTP attempt goes through the shared `LimitedHttpClient`
   (quotas, spacing, concurrency, cooldowns, retries) — see S07.
2. No redirects followed (`follow_redirects=False`); only allowlisted base
   URLs; LRCLIB external IDs must be positive decimal record IDs.
3. No secrets in logs, errors, diagnostics, or job payloads.
4. Unknown or prohibited redistribution defaults to link-only or disabled.
