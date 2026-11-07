# End-to-end tests (Playwright, S12)

Real-stack E2E against `docker compose`: real frontend + API with an
isolated seeded SQLite database and deterministic fixtures. No live
providers, no fixed sleeps, no shared mutable databases.

## Projects

- `chromium-desktop` (1280×720), `chromium-mobile` (Pixel 7),
  `webkit-mobile` (iPhone 14). WebKit needs OS deps; CI installs them with
  `playwright install --with-deps`.
- `setup` logs in once per role and stores session files in `.auth/`
  (gitignored) so specs avoid repeated logins — this also keeps the suite
  under the API login throttle. Never sign out a stored session (logout
  revokes it server-side and breaks parallel specs sharing the file).

## Run locally

```bash
docker compose down -v && docker compose up -d --build
docker compose exec -e MUSIC_GATHERINGS_BOOTSTRAP_PASSWORD='<pick-one>' \
  backend python -m app.cli create-admin --username root
SEED_ADMIN_PASSWORD='<same>' npm run --prefix tests/e2e seed
npx playwright test --project=setup --project=chromium-desktop --project=chromium-mobile
# webkit needs: npx playwright install --with-deps webkit (sudo required)
docker compose down -v
```

Always start from a fresh volume: login attempts are throttled per user
(verified working end-to-end by these very runs), and repeated runs on one
volume accumulate attempts. CI always uses a fresh volume. For rapid local
iteration, set `E2E_LOGIN_MAX_ATTEMPTS=100` (see `.env.example`).

## Conventions

- `loadSeed()` reads `.seed.json` (written by `seed.mjs`); specs fail fast
  with instructions if it is missing.
- Prefer accessible-role locators (`getByRole`, `getByLabel`) and
  condition-based waits (`toBeVisible`, `toHaveURL`); never `waitForTimeout`.
- `expectNoPageOverflow` asserts no horizontal page scroll at mobile widths.
- `expectTouchTargets` samples interactive controls (≥40px each dimension).
- `expectNoSeriousA11yViolations` runs axe-core (critical/serious only).
- Traces + screenshots are retained on failure (`test-results/`); the CI job
  uploads them as an artifact.
