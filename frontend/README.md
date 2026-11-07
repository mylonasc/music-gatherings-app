# UI module guide

The production UI is the studio replacement specified by
`../EPIC_UI_IMRPOVEMENTS.md` (#27), not a parallel theme or alternate application.

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
