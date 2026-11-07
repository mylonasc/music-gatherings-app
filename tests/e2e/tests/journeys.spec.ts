import { expect, test } from "@playwright/test";
import {
  expectNoPageOverflow,
  expectNoSeriousA11yViolations,
  expectTouchTargets,
  loadSeed,
} from "./helpers";

test.use({ storageState: ".auth/member.json" });

test("suggesting a track adds it to the jam list", async ({ page }) => {
  const title = `E2E Song ${Date.now()}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Suggest a track" }).click();
  await page.getByLabel("Title (optional)").fill(title);
  await page.getByLabel(/Genres/).fill("E2E");
  await page.getByRole("button", { name: "Suggest", exact: true }).click();
  await expect(page.getByText(title).first()).toBeVisible();
});

test("voting updates the score", async ({ page }) => {
  await page.goto("/");
  const card = page.locator(".track-card", { hasText: "Untitled track" });
  await expect(card.getByText("Votes 0")).toBeVisible();
  await card.getByRole("button", { name: "+1" }).click();
  await expect(card.getByText("Votes 1")).toBeVisible();
  await expect(card.getByRole("button", { name: "Clear" })).toBeVisible();
});

test("genre filter narrows the list", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Untitled track")).toBeVisible();
  await page.getByLabel("Genre").fill("Test");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByText("Blue Test Engine")).toBeVisible();
  await expect(page.getByText("Untitled track")).toBeHidden();
});

test("library search finds lyrics and opens the track", async ({ page }) => {
  const seed = loadSeed();
  await page.goto("/");
  await page.getByLabel("Search the library").fill("rolling down");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByText(/2 results/)).toBeVisible();
  await page.getByRole("link", { name: /Blue Test Train/ }).click();
  await expect(page).toHaveURL(new RegExp(`/tracks/${seed.renderedTrackId}`));
  await expectNoPageOverflow(page);
});

test("track views switch audience, guitar, and piano representations", async ({ page }) => {
  const seed = loadSeed();
  await page.goto(`/tracks/${seed.renderedTrackId}`);
  await expect(page.getByText("Rolling down", { exact: false }).first()).toBeVisible();
  await page.getByLabel("guitar", { exact: true }).check();
  await expect(page.getByText("chord chart", { exact: false }).first()).toBeVisible();
  await page.getByLabel("piano", { exact: true }).check();
  await expect(page.getByText("chord chart", { exact: false }).first()).toBeVisible();
  await expectNoPageOverflow(page);
});

test.describe("narrow viewport documents", () => {
  test.use({ viewport: { width: 360, height: 640 } });

  test("rendered documents scroll inside their panel without page overflow", async ({ page }) => {
    const seed = loadSeed();
    await page.goto(`/tracks/${seed.renderedTrackId}`);
    await page.getByLabel("guitar", { exact: true }).check();
    const panel = page.locator(".doc-panel").first();
    await expect(panel).toBeVisible();
    const containment = await panel.evaluate((element) => ({
      panelScrolls: element.scrollWidth > element.clientWidth + 1,
      pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
      hasChords: element.querySelectorAll(".chord, .chord-line").length,
    }));
    expect(containment.pageOverflow, "page must not scroll horizontally").toBeLessThanOrEqual(1);
    expect(containment.hasChords, "chord annotations preserved").toBeGreaterThan(0);
    expect(containment.panelScrolls, "wide notation scrolls inside its panel").toBe(true);
    await expectNoSeriousA11yViolations(page);
    await expectTouchTargets(page, "main button, main input, main select, header nav a");
  });
});
