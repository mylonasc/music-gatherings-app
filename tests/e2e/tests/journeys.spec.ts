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
  // Vote on a track this test suggests itself: parallel projects share the
  // seeded library, so asserting on seeded vote counts would race.
  const title = `E2E Vote ${Date.now()}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Suggest a track" }).click();
  await page.getByLabel("Title (optional)").fill(title);
  await page.getByRole("button", { name: "Suggest", exact: true }).click();
  const card = page.locator(".track-card", { hasText: title });
  await expect(card.getByRole("status")).toHaveText("0 thumbs up");
  await card.getByRole("button", { name: "Give thumbs up" }).click();
  await expect(card.getByRole("status")).toHaveText("1 thumbs up");
  await card.getByRole("button", { name: "Remove thumbs up" }).click();
  await expect(card.getByRole("status")).toHaveText("0 thumbs up");
  await expect(card.getByRole("button", { name: "Give thumbs up" })).toHaveAttribute("aria-pressed", "false");
});

test("genre filter narrows the list", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Untitled track")).toBeVisible();
  await page.getByText("Filters", { exact: true }).click();
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
  await expect(page.getByRole("region", { name: "rendered chord chart document" }).first()).toBeVisible();
  await page.getByLabel("piano", { exact: true }).check();
  await expect(page.getByRole("region", { name: "rendered chord chart document" }).first()).toBeVisible();
  await expectNoPageOverflow(page);
});

test.describe("narrow viewport documents", () => {
  test.use({ viewport: { width: 360, height: 640 } });

  test("rendered documents scroll inside their panel without page overflow", async ({ page }) => {
    const seed = loadSeed();
    await page.goto(`/tracks/${seed.renderedTrackId}`);
    await page.getByLabel("guitar", { exact: true }).check();
    // Wait for the guitar rendering itself, not just any panel: the previous
   // context's panel must not leak into the new resource identity.
    await expect(page.locator(".doc-panel .chord-line").first()).toBeVisible();
    const panel = page.getByRole("region", { name: "rendered chord chart document" }).first();
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
    await expectTouchTargets(page, "main button, main input:visible, main select:visible, header nav a");
  });

  test("plain lyrics stay inert and scroll locally at 320px", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 640 });
    await page.goto(`/tracks/${loadSeed().trackId}`);
    const lyrics = page.getByRole("region", { name: "lyrics document", exact: true });
    await expect(lyrics).toContainText("Rolling down the test track line");
    await expect(lyrics).toContainText("<script>window.fixtureExecuted=true</script>");
    expect(await lyrics.evaluate((element) => element.tagName)).toBe("PRE");
    await expect(lyrics.locator("script")).toHaveCount(0);
    expect(await lyrics.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
    await expectNoPageOverflow(page);
    await expectNoSeriousA11yViolations(page);
  });
});
