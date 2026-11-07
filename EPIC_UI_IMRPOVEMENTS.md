# Epic: Mobile-first UI replacement

Status: implemented on `implementation/ui-improvements`; final CI/PR evidence is
recorded below. Not a claim that unrelated backend release risks are resolved.
This filename intentionally retains the requested spelling. Issue links and
slice evidence are maintained below. A slice is not complete merely because
its code exists: its acceptance tests and review evidence must be recorded.

## Outcome and scope

Replace the rudimentary UI with a cohesive, accessible music workspace. Keep
React/TypeScript, generated API types, FastAPI authorization, durable jobs, and
the existing private service boundaries. Preserve working workflows, historical
provenance, and permission checks. Jam tracks remain the signed-in home.

Visual direction: **warm rehearsal studio** — warm off-white surfaces, ink text,
deep teal actions, restrained amber accents, generous rhythm, clear typography,
and readable music panels. No remote fonts, decorative stock imagery, or
animation essential to understanding state. Default to a light theme; dark mode
is not a prerequisite. Do not equate cosmetic polish with backend readiness.

Non-goals: new provider integrations, notation extraction, synchronized LRC
playback, offline/PWA, a plugin runtime, a backend rewrite, or fabricated music
capabilities. Existing backend risks #18–#26 remain explicit, not silently closed.

## UX inventory and information architecture

| Surface | Existing responsibilities | Replacement direction |
| --- | --- | --- |
| Login / access request | Credentials, approval, return destination | Focused branded form, useful errors, password-manager support |
| Jam tracks `/` | Crew list, filters, votes, suggestion, local search | Clear heading/actions, compact readable cards, distinct search/filter controls |
| Track detail | Metadata, versions, artifacts, audience/guitar/piano contexts | Reading workspace, isolated viewers, provenance and format labels |
| Online discovery `/search` | Provider selection, async search, explicit import | Separate discovery/configuration/job/result modules; never import on search |
| Crew `/crew` | Membership and access | Readable member/access states and role-aware actions |
| Admin `/admin` | Approval, profiles, processor/provider tests | Consistent sections, scoped forms, clear non-destructive test boundaries |

Use one semantic primary navigation: bottom navigation on phones, sidebar on
desktop. Admin remains role-gated. Account/sign-out controls are separate from
primary destinations. Preserve deep links and keyboard skip navigation.

## Architecture and extension contracts

- `frontend/src/components/`: accessible shared primitives, not domain logic.
  Keep the existing `components/ui` import facade while extracting implementations.
- `frontend/src/styles/`: design tokens and shared baseline; feature CSS is scoped
  by named classes, never broad `.app-main section` selectors.
- `frontend/src/app/`: shell, route composition, navigation configuration only.
- Feature modules own domain components/hooks; `lib/` owns HTTP and resource state.
  Use generated response types where available. Do not add a state library solely
  to restyle screens. Avoid giant page files and interchangeable stringly typed APIs.
- Track workspace: metadata/version/context selection is separate from document
  rendering. A typed viewer registry selects by supported kind/MIME/provenance;
  individual viewers own fetching/rendering and format controls. Adding a viewer
  normally touches its module, registry entry, and tests, not every track screen.
  Lyrics/LRC stay inert text; HTML must satisfy #21's trust boundary before inline
  rendering. Future tablature and sheet music remain separate capabilities with
  accessible download/reference fallbacks; no pretend PDF/tab support.
- Add-track workflows: independent method registry, manual suggestion, upload/link,
  provider discovery, import configuration, and job tracking. Share small typed
  inputs/results rather than one form with conditionals for every method. Consume
  backend capabilities through an authorized API; do not duplicate provider lists
  across components or publish private services. If API work is required, document
  the contract and test denials before claiming this extension seam is complete.
- Resource state must be keyed to identity: no stale track/document/user content
  during route changes, disabled queries, errors, or permission loss (#25).
- No changes to auth, ownership, job durability, or music identity semantics just
  to simplify presentation. Optional refinements go in `techdebt-ui-epic` with
  rationale, cost, and affected modules; critical work stays in its owning slice.

## Global acceptance bar

- Core UI fits 320 CSS px, 200% text enlargement, portrait/landscape, and safe-area
  insets. Wide notation scrolls inside a labeled, keyboard-focusable viewer.
- WCAG 2.2 AA target: contrast, visible focus, labels, keyboard operation, reduced
  motion, status announcements, focus after navigation/dialog dismissal, and no
  sticky bars obscuring focused controls. Normal touch targets are at least 44px.
- Every changed workflow covers loading, empty, success, error, and denial states.
  Preserve drafts on recoverable errors; prevent accidental double submissions.
- Dependencies remain locked; reusable primitives have unit tests. Feature slices
  include integration tests and relevant real-stack E2E journeys.
- No live upstream calls in ordinary tests, screenshot credentials, private user
  data, broad Docker-volume deletion, arbitrary sleeps, or automatic baseline updates.

## Implementation slices

Slices are independently reviewable commits/PRs after their prerequisites land.
Each must include code/docs/tests and list actual validation, screenshots, and
remaining limitations in its issue. Parallel work is possible only for independent
branches of this graph; execute sequentially here.

### UI-01 — UX inventory and visual specification
Dependencies: none. Scope: inventory above, screen/state map, baseline screenshot
capture recipe, target visual direction and module boundaries. Excludes feature
implementation. Acceptance: every current route/workflow accounted for, no feature
silently removed, device/evidence matrix defined. Tests: inspect existing routes,
components, E2E setup; capture baseline on isolated deterministic seeded data
before comparing replacement UI. Evidence: epic and baseline artifact location.

### UI-02 — Design system foundations
Dependencies: UI-01. Scope: tokens, typography, spacing, focus, buttons, fields,
cards, badges, loading/error/empty states; retain an import facade. Excludes shell
and feature redesign. Acceptance: semantic components, 44px controls, contrast,
reduced motion, no external asset requirement; field errors linked to controls.
Tests: primitive roles/labels/error/retry/disabled behavior, typecheck/build.

### UI-03 — Responsive shell and navigation
Dependencies: UI-02. Scope: extracted shell, typed navigation, active destinations,
mobile bottom navigation and desktop sidebar, account area, skip link. Excludes
feature-specific behavior. Acceptance: one primary nav, no duplicate focus targets,
deep links preserved, role-aware admin, safe-area/focus containment at 320px.
Tests: route/nav/admin/logout integration and mobile/desktop overflow screenshots.

### UI-04 — Resource state and feedback conventions
Dependencies: UI-02. Scope: identity-keyed query state, abort/race protection,
consistent retry/empty/error/denial presentations; coordinate with #25. Excludes
unneeded cache framework. Acceptance: old resources disappear immediately on key
change/disable/error, late responses cannot overwrite current data, retries work.
Tests: deferred request races, unmount/abort, text and JSON queries, denial recovery.

### UI-05 — Jam track library
Dependencies: UI-03, UI-04. Scope: list/card/filter/search/suggestion/vote modules,
metadata hierarchy and material badges. Acceptance: current metadata/actions retained,
clear local vs online search, keyboard/touch filters, no false optimistic success.
Tests: suggest/filter/vote/search/empty/denial, narrow and desktop screenshots.

### UI-06 — Extensible track workspace
Dependencies: UI-03, UI-04. Scope: track metadata/version/context components, typed
viewer registry, plain/LRC/chord viewers, provenance/format labels and fallback.
Prerequisite: resolve or safely avoid untrusted HTML rendering from #21; never
ship the existing unverified `dangerouslySetInnerHTML` assumption as a guarantee.
Acceptance: adding a viewer is localized; sheet/tab remain distinct future seams;
format/lineage obvious; documents do not overflow page or retain stale content.
Tests: registry matching/fallback, malicious text/HTML, guessed IDs/cross-crew,
context switching, wide music at 320px, keyboard and screenshot review.

### UI-07 — Add-track workflow boundaries
Dependencies: UI-04, UI-05. Scope: method registry and independently testable manual,
upload/reference and discovery entry modules using existing backend abilities.
Acceptance: adding a method is localized, validation/drafts/job state isolated,
capabilities explicit, no generic job bypass or provider auth duplication.
Tests: method switching, validation, cancellation/error/retry, duplicate submission,
authorization. Excludes new provider features and backend import-recovery rewrite.

### UI-08 — Search, discovery and import experience
Dependencies: UI-07. Scope: local search vs discovery, backend capability loading,
provider results, import options, job status/warnings/retry/open-track components.
Acceptance: searching never mutates library; import is explicit; provider identity
and rights warnings retained; unsupported providers are clearly unavailable.
Tests: deterministic provider search/import, failure/throttle/denial, backend API
contract tests for any capability endpoint, no live upstream calls.

### UI-09 — Account, crew and admin consistency
Dependencies: UI-03, UI-04. Scope: authentication/access, crew, admin section/form
composition using shared primitives. Acceptance: no lost admin operations, role
denial clear, password managers work, test tools cannot accidentally mutate library.
Tests: request/approval/login/logout, member/admin access, scoped provider/profile
forms, phone/desktop screenshots. Excludes changing authorization semantics.

### UI-10 — Device matrix and screenshot evidence infrastructure
Dependencies: UI-01; use UI-03 when validating replacement shell. Scope: extend
existing Playwright config/helpers, isolated seed lifecycle, HTML/gallery reports,
CI artifact links on PR checks. Acceptance: successful checkpoints as well as
failures captured with descriptive names; artifacts uploaded even on test failure;
retention documented; no PR write token/pull_request_target exposure required.
Tests: run matrix, inspect report/attachment paths and isolated setup. No invented
real-device guarantees; screenshot reporting must not wait for UI-11.

### UI-11 — Simulated journeys and visual regression
Dependencies: UI-05–UI-10. Scope: step-based musician/audience/admin journeys,
review gallery, curated visual baselines and accessibility/overflow checks.
Acceptance: browse/filter/vote; suggest/upload/link; discover/import/open; switch
music contexts/formats; denial/failure/recovery captured. Fixtures use original
music content, fixed identities, settled fonts/layout and reduced motion. Assert
behavior before snapshots; review baseline diffs manually, never auto-approve.
Tests: full matrix, targeted landscape and 320px, CI reports inspected; no skipped
flows hidden behind a green aggregate. Excludes live provider dependencies.

### UI-12 — Cutover and maintainability audit
Dependencies: UI-11. Scope: remove replaced legacy CSS/components after references
are verified, audit extension seams, docs and AGENTS commands, clean builds.
Acceptance: one production UI, no stale routes/duplicate primitives, documented
recipe for adding viewer/method/provider, CI green with inspectable evidence;
remaining backend risks and optional UI debt explicitly linked. No unrelated refactor.
Tests: full frontend/backend contracts/E2E/container CI; inspect generated screenshots.

## Device and evidence matrix

| Project | Engine / target | Coverage |
| --- | --- | --- |
| Desktop | Chromium, 1280×800 | Full behavioral journeys and curated screenshots |
| Pixel compact | Chromium, Pixel 5 | Full core journeys |
| Pixel standard | Chromium, Pixel 7 | Full core journeys |
| iPhone small | WebKit, iPhone SE | Full core journeys |
| iPhone standard | WebKit, iPhone 14 | Full core journeys |
| iPhone large | WebKit, iPhone 14 Pro Max | Full core journeys |
| Minimum layout | Chromium/WebKit, 320px | Shell, forms, wide document containment |
| Landscape | Pixel 7 / large iPhone | Navigation, keyboard-focus visibility and document workspace |

Emulation checks browser/viewport/touch behavior, not physical-device fidelity or
virtual keyboard behavior. Real device checks remain a release checklist item.
Use Playwright built-in descriptors verified against the locked installed version.

Screenshots: `test.step` checkpoints with `testInfo.attach`; include project,
journey and checkpoint in names. Produce a browsable HTML report plus gallery;
upload report and raw images in CI on success/failure with documented retention.
Use CI artifacts/check summaries linked from PRs; automatic image posting requires
separate least-privilege review. Visual baselines are engine/project-specific,
generated in pinned CI/browser environments, and only updated through reviewed
changes. Keep failure traces/screenshots. Do not overwrite user data to reseed.

## Validation and tracking

Existing verified commands: `npm test --prefix frontend`,
`npm run typecheck --prefix frontend`, `npm run build --prefix frontend`,
`npm test --prefix tests/e2e` (requires isolated stack and seed; see E2E README),
plus backend/services/Compose checks in AGENTS.md. New commands must be implemented
and run before being called verified. CI success is evidence only for its exact SHA.

Issue links, per-slice status, evidence, and any optional `techdebt-ui-epic` follow-ups
will be maintained as implementation proceeds.

## Implementation evidence

- UI-01: route/state inventory above; historical desktop/phone captures in
  `docs/ui-baseline/`, captured before replacement against isolated fixtures.
- UI-02/UI-03: design tokens, semantic primitives, studio shell with one primary
  navigation, active track ancestry, compact phone header, safe-area insets;
  short landscape navigation flows with the page to avoid hiding focused fields.
- UI-04: render-time resource identity check, abort/late-response protection,
  query-disable and denial tests for JSON/text; job state keyed to job identity.
- UI-05: isolated track cards/votes and filter module; collapsible secondary
  filters keep the phone list approachable. Local search remains distinct.
- UI-06: reading contexts and version selection, inventory, material attachment,
  and typed viewer dispatch are separate modules. Plain/LRC remain distinct;
  music HTML is strictly sanitized with pinned DOMPurify. Unsupported sheet/tab
  formats have download/reference fallbacks, not invented preview support.
- UI-07/UI-08: dedicated method-entry page, draft-preserving manual/material forms,
  multipart CSRF client, independent result/import controllers, scoped idempotency
  keys, authorized `/api/v1/providers` capability endpoint. Built-in provider
  names/default URLs are registered once in `backend/app/core/providers.py`.
- UI-09: branded auth layout, crew selection and member cards, keyboard-operated
  admin tabs/panels; existing approval/profile/test/audit operations preserved.
- UI-10/UI-11: six browser projects; named success/failure checkpoint attachments,
  standalone HTML gallery, retained failure traces, 12 curated visual baselines,
  320px/landscape/200% text, accessibility/overflow assertions, and PR check-summary
  artifact links. All run in a digest-pinned Playwright 1.57.0 Noble image.
- UI-12: one production shell/styles path, feature extension guide in
  `frontend/README.md`, safe disposable-stack runner and agent guidance updated.

Local validation: **187 Playwright tests passed** in a fresh isolated run without
baseline updates; **31 frontend tests**, **95 backend tests**, frontend production
build/typecheck, backend Ruff and mypy passed. Screenshot generation was a separate
explicit review run, followed by normal comparison. Screenshots for all six
projects were visually inspected. CI run
[42409929628](https://github.com/mylonasc/music-gatherings-app/actions/runs/42409929628)
passed all seven jobs at head `20c0609`, including 187 browser checks with no
retries and a downloaded/verified 90-image gallery. PR #41 contains preview images
and current check results; later commits require their own green checks.

Optional maintainability follow-ups: #40 (`techdebt-ui-epic`), linked to parent
#27. Remaining backend security/durability/recovery issues are not automatically
closed by these UI changes; in particular #21 also covers backend trust/serving
boundaries, beyond this frontend sanitation.

## Issue index

Parent: #27.

- [x] UI-01: #28
- [x] UI-02: #29
- [x] UI-03: #30
- [x] UI-04: #31
- [x] UI-05: #32
- [x] UI-06: #33
- [x] UI-07: #34
- [x] UI-08: #35
- [x] UI-09: #36
- [x] UI-10: #37
- [x] UI-11: #38
- [x] UI-12: #39

Checked means implemented and validated on the branch, not merged or physically
device-certified. PR #41 closes these issues when merged. Optional debt #40 stays open.
