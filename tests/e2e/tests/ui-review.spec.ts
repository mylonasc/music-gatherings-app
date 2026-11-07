import { expect, test } from "@playwright/test";
import { checkpoint, loginVisual } from "./checkpoint";
import { expectNoPageOverflow, expectNoSeriousA11yViolations, loadSeed } from "./helpers";

test("visual baseline: sign-in", async ({ page }, info) => {
  await loginVisual(page);
  await checkpoint(page, info, "01-sign-in");
});

test.describe("member review journeys", () => {
  test.use({ storageState: ".auth/member.json" });

  test("crew member browses, filters and votes on a new suggestion", async ({ page }, info) => {
    await page.goto("/");
    await page.getByText("Filters", { exact: true }).click();
    await page.getByLabel("Genre", { exact: true }).fill("Test");
    await page.getByRole("button", { name: "Apply", exact: true }).click();
    await expect(page.getByText("Blue Test Engine — The Determinists", { exact: true })).toBeVisible();
    await checkpoint(page, info, "00-filtered-library");
    await page.getByRole("button", { name: "Suggest a track", exact: true }).click();
    const title = `Voting fixture ${info.project.name} ${Date.now()}`;
    await page.getByLabel("Title (optional)").fill(title);
    await page.getByLabel("Genres (comma-separated, optional)").fill("Test");
    await page.getByRole("button", { name: "Suggest", exact: true }).click();
    const card = page.locator(".library-card", { hasText: title });
    await expect(card.getByText("Votes 0")).toBeVisible();
    await card.getByRole("button", { name: "+1", exact: true }).click();
    await expect(card.getByText("Votes 1")).toBeVisible();
    await checkpoint(page, info, "00-crew-vote");
    await expectNoSeriousA11yViolations(page);
  });

  test("musician suggests a song, uploads lyrics and links sheet music", async ({ page }, info) => {
    const title = `Review song ${info.project.name}`;
    await test.step("Choose a method and suggest a track", async () => {
      await page.goto("/add");
      await expect(page.getByRole("heading", { name: "Bring a song" })).toBeVisible();
      await checkpoint(page, info, "02-add-methods");
      await page.getByLabel("Title (optional)").fill(title);
      await page.getByLabel("Artist (optional)").fill("The Fixture Crew");
      await page.getByRole("button", { name: "Suggest", exact: true }).click();
      await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    });
    await test.step("Upload original plain lyrics", async () => {
      await page.getByText("Add materials to this track", { exact: true }).click();
      await page.getByLabel("File", { exact: true }).setInputFiles({ name: "review-lyrics.txt", mimeType: "text/plain", buffer: Buffer.from("Original review fixture lyric\n<script>not executed</script>\n") });
      await page.getByRole("button", { name: "Save material" }).click();
      await expect(page.getByRole("region", { name: "lyrics document", exact: true })).toContainText("Original review fixture lyric");
      await expect(page.locator("pre script")).toHaveCount(0);
      await checkpoint(page, info, "03-uploaded-lyrics");
    });
    await test.step("Link sheet music without claiming a preview", async () => {
      await page.getByText("Add materials to this track", { exact: true }).click();
      await page.getByLabel("Material type").selectOption("sheet_music");
      await page.getByLabel("Attach by").selectOption("reference");
      await page.getByLabel("Source URL").fill("https://example.test/personal-score.pdf");
      await page.getByRole("button", { name: "Save material" }).click();
      await page.getByLabel("piano", { exact: true }).check();
      await expect(page.getByRole("region", { name: "lyrics document", exact: true })).toHaveCount(0);
      await expect(page.getByRole("link", { name: "open external reference" }).first()).toHaveAttribute("href", "https://example.test/personal-score.pdf");
      await checkpoint(page, info, "04-linked-sheet-music");
      await expectNoSeriousA11yViolations(page);
    });
  });

  test("audience reads music and changes context without page overflow", async ({ page }, info) => {
    await page.goto(`/tracks/${loadSeed().trackId}`);
    await expect(page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Jam tracks" })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("region", { name: "lyrics document", exact: true })).toContainText("Rolling down");
    await expect(page).toHaveScreenshot("track-reading.png", { fullPage: true, animations: "disabled" });
    await checkpoint(page, info, "05-audience-reading");
    await page.getByLabel("guitar", { exact: true }).check();
    await expect(page.getByText("Nothing available for the guitar view yet.")).toBeVisible();
    await expect(page.getByRole("region", { name: "lyrics document", exact: true })).toHaveCount(0);
    await checkpoint(page, info, "06-unavailable-context");
    await page.setViewportSize({ width: 320, height: 568 });
    await page.getByLabel("audience", { exact: true }).check();
    await expect(page.getByRole("region", { name: "lyrics document", exact: true })).toBeVisible();
    await checkpoint(page, info, "07-minimum-width");
    await expectNoSeriousA11yViolations(page);
  });

  test("discovery shows recoverable throttling and imports only after confirmation", async ({ page }, info) => {
    await page.goto("/search");
    await page.getByLabel("Song or artist").fill("blue");
    await expect(page.getByLabel("fake", { exact: true })).toBeEnabled();
    await page.route("**/api/v1/search/online", (route) => route.fulfill({ status: 429, contentType: "application/json", body: JSON.stringify({ detail: "Please wait before searching again." }) }));
    await page.getByRole("button", { name: "Search online" }).click();
    await expect(page.getByRole("alert")).toContainText("Please wait");
    await checkpoint(page, info, "08-throttled-discovery");
    await page.unroute("**/api/v1/search/online");
    await page.getByRole("button", { name: "Search online" }).click();
    const importing = page.getByRole("button", { name: /Import “Blue Test Train/ });
    await expect(importing).toBeVisible({ timeout: 30_000 });
    await checkpoint(page, info, "09-discovery-results");
    await importing.click();
    await expect(page.getByRole("link", { name: "Open the track" })).toBeVisible({ timeout: 30_000 });
    await checkpoint(page, info, "10-import-result");
  });

  test("permission denial does not retain the previous track", async ({ page }, info) => {
    await page.goto(`/tracks/${loadSeed().trackId}`);
    await expect(page.getByRole("heading", { name: "Blue Test Engine", exact: true })).toBeVisible();
    await page.goto(`/tracks/${loadSeed().hiddenTrackId}`);
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page.getByText("Rolling down")).toHaveCount(0);
    await checkpoint(page, info, "11-denied-track");
  });

  test("landscape and large text keep navigation and forms operable", async ({ page }, info) => {
    const viewport = page.viewportSize()!;
    await page.setViewportSize({ width: Math.max(viewport.width, viewport.height), height: Math.min(viewport.width, viewport.height) });
    await page.goto("/add");
    await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
    await expect(page.getByRole("heading", { name: "Bring a song" })).toBeVisible();
    await page.getByLabel("Title (optional)").focus();
    await expect(page.getByLabel("Title (optional)")).toBeFocused();
    const field = await page.getByLabel("Title (optional)").boundingBox();
    const nav = await page.getByRole("navigation", { name: "Primary" }).boundingBox();
    expect(field).not.toBeNull();
    const fixedNav = await page.getByRole("navigation", { name: "Primary" }).evaluate((el) => getComputedStyle(el).position === "fixed");
    if (nav && fixedNav) expect(field!.y + field!.height).toBeLessThanOrEqual(nav.y);
    await expectNoPageOverflow(page);
    await checkpoint(page, info, "12-landscape-large-text");
  });
});

test.describe("admin review", () => {
  test.use({ storageState: ".auth/admin.json" });
  test("admin navigates diagnostics with keyboard", async ({ page }, info) => {
    await page.goto("/admin");
    const requests = page.getByRole("tab", { name: "requests", exact: true });
    await requests.focus(); await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("tab", { name: "providers", exact: true })).toBeFocused();
    await expect(page.getByRole("heading", { name: "Provider status" })).toBeVisible();
    await checkpoint(page, info, "13-provider-diagnostics");
    await expectNoSeriousA11yViolations(page);
  });
});
