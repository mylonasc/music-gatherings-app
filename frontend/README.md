# UI module guide

The production UI is the studio replacement delivered by
[UI epic #27](https://github.com/mylonasc/music-gatherings-app/issues/27) and PR #41,
not a parallel theme or alternate application. All twelve implementation slices
are complete; optional maintainability refinements remain in
[#40](https://github.com/mylonasc/music-gatherings-app/issues/40).

## Ownership

- `styles/tokens.css`: shared color, typography, spacing and shape tokens.
- `App.css`: baseline controls/layout/feedback; do not style arbitrary descendant
  sections. Feature-specific layouts belong to their feature, e.g. `tracks.css`.
- `components/ui.tsx`: shared semantic primitives and field/error associations.
- `app/`: route and shell composition, active role-aware primary navigation.
- `lib/`: typed HTTP/CSRF, identity-keyed resource state, job polling, safe music
  HTML sanitation. API types are generated, not hand-edited.
- `features/tracks/`: library cards, votes, suggestion, track reading contexts.
- `features/tracks/viewers/`: typed document dispatch and inert/sanitized readers.
- `features/adding/`: method entry registry, manual entry composition, material
  attachment forms. Methods own their drafts and validation.
- `features/search/`: discovery composition, result cards, isolated per-hit import
  controllers. Backend `/api/v1/providers` supplies authorized capabilities;
  frontend modules do not carry their own lists of provider IDs.

## Extend without cross-cutting edits

**Viewer:** add a component implementing `ViewerProps` and one ordered registry
entry in `viewers/DocumentViewer.tsx`. Match kind **and** MIME where relevant.
Add selection/fallback/security tests and a fixture-backed reading journey. Do
not reinterpret raw lyrics, LRC, tablature, or opaque PDFs as HTML. Existing HTML
viewers sanitize a strict inert tag/attribute allowlist even for processor output.
Never remove the backend file authorization boundary. No PDF/tab conversion or
synchronized LRC playback is currently promised.

**Adding method:** add a dedicated feature component/route, an entry in
`adding/methods.ts`, and tests. Do not put provider-specific forms into the manual
suggestion module. Attach uploaded/linked artifacts to an explicit musical version;
file and link workflows use the same authenticated API and CSRF client.
Network interruption after a write can be ambiguous: check saved materials before
retrying. Full durable import resumption remains backend issue #23.

**Provider:** implement the private ingestion contract, then register the provider
in `backend/app/core/providers.py` (shared defaults and validated names). Discovery consumes its capabilities
without a frontend provider-list edit. Never turn capability availability into a
promise that the upstream currently works. Search and import remain distinct jobs.

Resource hooks clear data synchronously when identity changes or a query is
disabled. Do not copy query result arrays into page-level state: local card vote
state is scoped to the card and discarded when the result set changes. Abort and
ignore outdated responses; test permission loss and late-response races.

## Validation

From repository root: `npm test --prefix frontend`,
`npm run typecheck --prefix frontend`, `npm run build --prefix frontend`.
Browser/device/evidence instructions: `../tests/e2e/README.md`. New API schemas:
start the backend and run `OPENAPI_URL=http://localhost:<port>/openapi.json npm run
gen:api --prefix frontend`. Keep lockfiles and generated types committed.

Optional refinements, not architecture/security deferrals: #40 (`techdebt-ui-epic`).
Real-device usability, virtual keyboards, and manual screen-reader checks remain
release review items beyond emulated browser/axe coverage.

## Mobile HTTP compatibility and diagnostics

LAN development URLs such as `http://192.168.x.x` are not secure contexts even
though `http://localhost` is considered trustworthy by browsers. Never invoke
HTTPS-only APIs during rendering. Import idempotency keys use lazy
`crypto.getRandomValues` (also available on HTTP); if unavailable, omit the optional
client key rather than crash or introduce a predictable security token. These are
non-secret deduplication keys, not authentication credentials. Production still
requires HTTPS and Secure session cookies.

Root and route error boundaries provide recovery instead of unmounting the whole
UI into a blank screen. Route failures retain navigation; changing routes resets
the route boundary. Global JavaScript/rejection errors and failed HTTP requests
record only a redacted category, route template, status/timing and timestamp.

Open **Crew → Troubleshooting and diagnostics**, or `/diagnostics`, to enable
request timings in the current tab, reproduce, then inspect/download the JSON
report before reloading. A crash screen offers the same download directly. The
report includes secure-context/API availability, viewport, browser user agent,
and built JS asset fingerprints. Its bounded 40-event buffer stays in memory;
there is no automatic upload, local/session storage, or backend telemetry endpoint.
Reloading clears it and disables successful-request recording. Never add query
strings, IDs, song content, credentials, raw exception messages/stacks, cookies,
headers or request bodies. See `lib/diagnostics.ts` and its privacy tests.

## Removing tracks

`can_remove` is computed by the backend for each crew listing/entry. Only the
adding user or an admin sees Delete controls; the DELETE endpoint independently
enforces ownership, crew authorization and CSRF. Confirmation removes the listing
and votes from that crew. It does **not** globally erase tracks, files, versions,
or another crew's listing. A removed member loses access when no remaining crew
grants visibility. Permanent orphan/file cleanup is a separate storage concern.

## Compact library reactions

Library cards keep title, requester/genres/version count, and material badges in
one compact summary, with actions alongside it. The bin is visually small but its
button retains a 44px target, a track-specific accessible label, and confirmation.
Cards expand naturally for long metadata or enlarged text rather than clipping it.

`UpvoteToggle` is the only library reaction control: press to give a thumbs up,
press again to remove your own reaction. `aria-pressed`, styling and the live count
reflect the confirmed server state, not an optimistic success. Pending requests
are locked against double taps; failures keep the prior reaction/count visible.
The additive `upvote_count` API field counts positive votes only. Legacy negative
votes and `vote_score` remain intact for compatibility; they are not displayed as
thumbs-up counts. A legacy downvote can be replaced by giving a thumbs up.
