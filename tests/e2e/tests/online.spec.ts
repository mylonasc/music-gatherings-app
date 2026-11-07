import { expect, test } from "@playwright/test";
import { expectNoPageOverflow } from "./helpers";

test.use({ storageState: ".auth/member.json" });

test("online search finds the fake provider hit and imports it", async ({ page }) => {
  await page.goto("/search");
  await expect(page.getByRole("checkbox", { name: "LRCLIB", exact: true })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: /genius/i })).toHaveCount(0);
  await page.getByLabel("Song or artist").fill("blue");
  // Fake provider only (the default): deterministic, no live upstream.
  await page.getByRole("button", { name: "Search online" }).click();
  await expect(page.getByText(/Blue Test Train/).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /Import “Blue Test Train/ }).click();
  const openLink = page.getByRole("link", { name: "Open the track" });
  await expect(openLink).toBeVisible({ timeout: 30_000 });
  await expect(openLink).toHaveAttribute("href", /\/tracks\//);
  await openLink.click();
  await expect(page.getByRole("heading", { name: "Blue Test Train" })).toBeVisible();
  await expectNoPageOverflow(page);
});

test("disabled provider is explicitly unavailable and cannot start discovery", async ({ page }) => {
  await page.goto("/search");
  await page.getByLabel("Song or artist").fill("blue");
  // Capabilities are queried privately; no live upstream search is involved.
  await page.getByLabel("fake", { exact: false }).uncheck();
  await expect(page.getByLabel("ultimate guitar", { exact: false })).toBeDisabled();
  const searchButton = page.getByRole("button", { name: "Search online" });
  await expect(searchButton).toBeDisabled();
  await expect(page.getByText("Unavailable for discovery")).toBeVisible();
});
