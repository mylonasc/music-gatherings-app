# Repository guidance for agents

## Current state and source of truth

S01 is implemented on `main`: FastAPI backend skeleton (`backend/`), React
skeleton (`frontend/`), Compose network/volume (`docker-compose.yml`), CI
(`.github/workflows/ci.yml`), and docs. Later slices are still plans. Read
`EPIC_APP_BOOTSTRAP.md` for the architecture, stable S01–S16 slices, acceptance
criteria, and dependency graph. Consult the linked GitHub parent/slice issues
for current status and decisions.

Implement only the requested scope and respect slice prerequisites. Do not silently
turn working defaults or unsupported provider capabilities into confirmed promises.
Do not commit/push, create external resources, or add unrelated infrastructure
unless the task authorizes it. Preserve unrelated user changes.

## Architecture rules

- Main backend: Python/FastAPI modular monolith for auth, crews, library, local
  search, authorization, artifact serving, jobs, and orchestration.
- Private HTTP microservices: provider ingestion and normalization/post-processing.
  No user auth duplication and no public host ports for these services.
- SQLite + SQLAlchemy/Alembic initially; FTS5 with explicit typo-tolerant search.
  Enforce foreign keys, ownership, unique constraints, and short write transactions.
- Immutable objects behind an object-store interface; local named Docker volume
  initially. Never expose raw filesystem paths or mount the object store publicly.
- Separate track identity, musical version, source artifact, and processing revision.
  Metadata may be missing; genres are multi-label; piano suitability is tri-state.
- Keep chords, tablature, and sheet music distinct. Do not claim a transform supports
  formats it cannot safely handle. Preserve raw input and record derivation lineage.
- Use durable, idempotent jobs for external work; no Redis/Celery requirement initially.

## Security and provider integration

- Reuse main-app user/crew authorization for every API, file, search, job, and agent
  tool. Test guessed IDs and cross-crew access, not just authenticated happy paths.
- Passwords use Argon2id; sessions require secure cookies, CSRF protection, expiry,
  and revocation. No default admin password or committed credentials.
- Provider terms, package maintenance, credentials, and rights must be verified.
  Unknown/prohibited redistribution defaults to link-only or disabled behavior.
  Never bypass upstream access restrictions.
- Every outbound provider HTTP attempt must pass configurable per-service limits,
  including retries, redirects, and pagination. Enforce overall/operation quotas,
  concurrency, spacing, cooldowns, and bounded retries. Admin tests cannot bypass them.
- Prevent arbitrary URL fetching/SSRF, path traversal, unsafe inline HTML, unlimited
  downloads/parsing, and secret leakage. Treat external/user content as untrusted.
- Agents start read-only with scoped, revocable credentials and audited tools; never
  grant direct database/filesystem/shell access or treat document text as instructions.

## Frontend and testing

- React/TypeScript, feature-oriented modules, reusable accessible primitives,
  generated API types, and consistent server-state handling.
- Mobile first: 320 CSS px minimum layout, touch-friendly controls, keyboard/focus
  support, and WCAG 2.2 AA target. Jam tracks are the default authenticated view.
- Preserve chord/lyric alignment. Wide music documents scroll within their own
  region; the overall page must not overflow. Test empty/loading/error/denial states.
- Add unit/integration/contract tests alongside changes. Use real SQLite/FTS5 and
  temporary object storage for persistence tests.
- Use Playwright for real-stack E2E with deterministic fake providers, isolated seeded
  data, desktop/mobile Chromium, and mobile WebKit. Do not depend on live upstream
  sites in ordinary CI. Live checks are opt-in and obey the same limits.
- Prefer accessible-role locators and condition-based waits; no arbitrary sleeps.
  Retain failure traces/screenshots and include accessibility/overflow checks.
- Run the commands actually defined by the implementation/tooling. Until those
  exist, do not invent commands or report tests as passing. Report what ran and any
  blockers honestly. Keep dependencies locked and document new configuration.
- Verified S01 commands (run from repo root):
  `python3 -m pytest backend/tests -q`, `python3 -m ruff check backend`,
  `python3 -m mypy backend/app`, `npm ci --prefix frontend`,
  `npm run typecheck --prefix frontend`, `npm run build --prefix frontend`,
  `docker compose config --quiet`, `docker compose up --build`.
  Use `make` targets or the `README.md` equivalents where convenient.

## Workflow and maintaining this file

1. Inspect repository state and the relevant issue/slice before editing.
2. Keep changes reviewable and aligned with existing code patterns. Avoid speculative
   abstractions, unrelated refactors, and unnecessary service/infrastructure splits.
3. Implement acceptance criteria with tests; document API, migration, config,
   operational, and user-visible changes. Update issue dependencies if scope changes.
4. In the final summary, state outcomes, validation performed, and remaining risks.
5. **Maintain `AGENTS.md` as part of any change that alters repository layout,
   development/test commands, architectural boundaries, security rules, or agent
   workflow.** Add verified commands once tooling exists; remove stale guidance.
   Keep it concise and actionable, not a task diary. Keep enduring design decisions
   and slice dependencies synchronized with `EPIC_APP_BOOTSTRAP.md` and GitHub issues.
   If nested `AGENTS.md` files are introduced, describe their scope and avoid
   conflicting rules. Do not silently rewrite product scope while updating guidance.
