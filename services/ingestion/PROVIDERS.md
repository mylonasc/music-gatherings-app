# Provider integrations: capability and rights matrix

Checked 2026-11-07 via web research (package registries, official docs, ToS).

## Genius (`services/ingestion/genius/`)

- Transport: official developer API only, `https://api.genius.com`
  (see https://docs.genius.com). Free client access token in
  `GENIUS_ACCESS_TOKEN`.
- Permitted: `GET /search` (song/artist metadata) and `GET /songs/:id`
  (metadata). The API intentionally does **not** serve lyric text.
- Prohibited/avoided: scraping `genius.com` song pages for lyrics violates
  Genius' Terms of Service (stated by the `lyricsgenius` project itself, which
  scrapes via BeautifulSoup). We therefore do **not** depend on
  `lyricsgenius` and never scrape song pages.
- Consequence: `fetch` returns metadata + source URL with
  `storage_allowed: false` on every artifact slot — i.e. **reference-only**.
  Nothing from Genius is stored locally.
- Credentials: `GENIUS_ACCESS_TOKEN` (required for search/fetch; without it
  the service reports `configured: false` and returns 503 with a structured
  `provider_unavailable`/`not_configured` error — never a secret leak).

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
   URLs; external IDs validated (Genius song IDs are numeric).
3. No secrets in logs, errors, diagnostics, or job payloads.
4. Unknown or prohibited redistribution defaults to link-only or disabled.
