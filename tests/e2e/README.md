# Real-stack browser tests and visual review

From the repository root on Linux with Docker Compose and Node 24 installed:

```bash
bash tests/e2e/run-isolated.sh
# A selected journey (still runs authentication setup):
bash tests/e2e/run-isolated.sh tests/ui-review.spec.ts
```

This creates a unique `mg-ui-e2e-<pid>` project, checks it does not already exist,
seeds only its disposable volume, and cleans up only that project on exit. It
does **not** reset your normal Compose volume. Defaults: frontend 3200/backend
8200; override `UI_E2E_FRONTEND_PORT` and `UI_E2E_BACKEND_PORT` if busy. Do not
run two suites in the same checkout: `.auth/` and `.seed.json` are run-scoped.

## Device matrix

- `chromium-desktop`: 1280×720 Chromium.
- `pixel-compact`: Pixel 5, Chromium.
- `chromium-mobile`: Pixel 7, Chromium (existing project name retained).
- `iphone-small`: iPhone SE, 320×568 WebKit.
- `webkit-mobile`: iPhone 14, WebKit (existing project name retained).
- `iphone-large`: iPhone 14 Pro Max, WebKit.

Every project runs the behavioral suite. Review journeys additionally exercise
320px, landscape, and 200% text. Device descriptors and screenshots are browser
emulation, **not** physical-device/virtual-keyboard certification.

Mutation journeys are serialized (`workers: 1`) because the isolated run shares
a library. Tests create their own mutable tracks; shared seeded tracks are
read-only. Admin approval is scoped to the exact newly created user. Only the
isolated E2E stack raises login admission to 100 for the larger matrix; normal
settings and provider outbound limits are unchanged. Fake provider fixtures are
original content; ordinary tests never search/fetch live upstreams.

## Inspecting screenshots

- `review-gallery/index.html`: standalone gallery, including **successful**
  named journey checkpoints and failures; click images for full resolution.
- `playwright-report/index.html`: test steps, screenshot attachments, and failures.
- `test-results/`: raw checkpoint images and retained failure traces/screenshots.
- CI uploads all three directories on success **and** failure for 14 days. A link
  appears in the E2E job/check summary, accessible from the PR checks. Download,
  extract, and open the gallery or run `npx playwright show-report` from this folder.
  No write token or untrusted `pull_request_target` workflow posts comments.

`ui-review.spec.ts` captures adding, uploading/linking distinct music materials,
reading/context switching, browsing/filtering/voting, explicit importing,
throttling recovery, authorization denial, landscape/large text, and admin
keyboard navigation. Screenshots contain only disposable fixture users, not real
credentials or personal library data. Traces contain test sessions: treat even
test artifacts accordingly and keep their retention bounded.

## Visual baselines

Curated sign-in and seeded track-reading baselines live beside `ui-review.spec.ts`
in its `-snapshots/` directory, per project/engine. Assertions run normally in CI;
missing/changed baselines fail. **Never update them automatically in CI.**

Both CI and the isolated script run Playwright 1.57.0 in the same digest-pinned
Noble image (see script/workflow). Native host WebKit dependencies are not needed.
Changing the browser/image/fonts requires deliberate baseline review:

```bash
bash tests/e2e/run-isolated.sh tests/ui-review.spec.ts --update-snapshots
git diff --stat tests/e2e/tests/ui-review.spec.ts-snapshots
# Inspect every changed image and the gallery, then run again without updates.
```

Do not weaken thresholds or mask real content to make tests green. Behavior and
accessibility assertions precede snapshots. New checkpoints use `checkpoint.ts`
and `test.step`; prefer accessible-role locators and condition-based waits. No
arbitrary sleeps. The `setup` project stores member/admin sessions once; logout
tests create separate sessions rather than revoke shared ones.
