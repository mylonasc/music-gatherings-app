import { expect, test } from "@playwright/test";
import { expectNoPageOverflow, expectNoSeriousA11yViolations, expectTouchTargets, loadSeed } from "./helpers";

test.use({ storageState: ".auth/member.json" });

test("seeded tracks render with metadata on the default route", async ({ page }) => {
  await page.goto("/");
  const card = page.locator(".track-card", { hasText: "Blue Test Engine" });
  await expect(card.getByText("Blue Test Engine — The Determinists")).toBeVisible();
  await expect(card.getByText("Test", { exact: true })).toBeVisible();
  await expect(card.getByRole("status")).toHaveText("1 thumbs up");
  await expect(card.getByRole("button", { name: "Remove thumbs up" })).toHaveAttribute("aria-pressed", "true");
  await expect(card.getByText(/piano-friendly/)).toBeVisible();
  await expect(page.getByText("Untitled track")).toBeVisible();
  await expectNoPageOverflow(page);
});

test("track detail shows versions and material links", async ({ page }) => {
  const seed = loadSeed();
  await page.goto(`/tracks/${seed.trackId}`);
  await expect(page.getByRole("heading", { name: "Seeded" })).toBeVisible();
  const download = page.getByRole("link", { name: /download/ });
  await expect(download).toBeVisible();
  await expectNoPageOverflow(page);
  await expectNoSeriousA11yViolations(page);
});

test("jam tracks page has no serious accessibility violations", async ({ page }) => {
  await page.goto("/");
  await expectNoSeriousA11yViolations(page);
  await expectTouchTargets(page, "main button, header nav a");
});
