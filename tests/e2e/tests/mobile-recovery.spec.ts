import { expect, test } from "@playwright/test";
import { checkpoint } from "./checkpoint";
import { expectNoPageOverflow, expectNoSeriousA11yViolations, loadSeed } from "./helpers";

test("LAN HTTP search results and import work without secure-context APIs", async ({ page, baseURL }, info) => {
  // Docker /etc/hosts maps this ordinary hostname to 127.0.0.1. Browsers must
  // actually treat it as insecure, unlike localhost or any 127.x loopback URL.
  const origin = new URL(baseURL!); origin.protocol = "http:"; origin.hostname = "lan-http.test";
  await page.goto(new URL("/login", origin).href);
  await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.isSecureContext)).toBe(false);
  expect(await page.evaluate(() => typeof crypto.randomUUID)).toBe("undefined");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.name));
  const seed = loadSeed();
  await page.getByLabel("Username").fill(seed.users.member.username);
  await page.getByLabel("Password", { exact: true }).fill(seed.users.member.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Jam tracks", exact: true })).toBeVisible();
  await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Online search" }).click();
  await page.getByLabel("Song or artist").fill("blue");
  await page.getByRole("button", { name: "Search online" }).click();
  await expect(page.getByRole("button", { name: /Import “Blue Test Train/ })).toBeVisible({ timeout: 30_000 });
  await checkpoint(page, info, "lan-http-search-results");
  await page.getByRole("button", { name: /Import “Blue Test Train/ }).click();
  await expect(page.getByRole("link", { name: "Open the track" })).toBeVisible({ timeout: 30_000 });
  expect(errors).toEqual([]);
  await expectNoPageOverflow(page);
});

test.describe("recovery and removal", () => {
  test.use({ storageState: ".auth/member.json" });

  test("render failures retain navigation and expose a private diagnostic report", async ({ page }, info) => {
    await page.goto("/diagnostics");
    await page.getByLabel("Record request timings for this tab").check();
    await page.route("**/api/v1/providers", (route) => route.fulfill({ status: 200, contentType: "application/json", body: '{}' }));
    await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Online search" }).click();
    await expect(page.getByRole("heading", { name: "Something went wrong", exact: true })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
    const href = await page.getByRole("link", { name: "Download diagnostic report" }).getAttribute("href");
    const report = JSON.parse(decodeURIComponent(href!.split(",")[1]));
    expect(report.events.some((event: { kind: string }) => event.kind === "render")).toBe(true);
    await checkpoint(page, info, "render-error-recovery");
    await expectNoSeriousA11yViolations(page);
    await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Crew", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Jam crew", exact: true })).toBeVisible();
    await page.getByRole("link", { name: "Troubleshooting and diagnostics" }).click();
    await expect(page.getByRole("heading", { name: "Diagnostics", exact: true })).toBeVisible();
  });

  test("a member can cancel then delete their own track listing", async ({ page }, info) => {
    const title = `Removal fixture ${info.project.name}`;
    await page.goto("/add");
    await page.getByLabel("Title (optional)").fill(title);
    await page.getByRole("button", { name: "Suggest", exact: true }).click();
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Delete track", exact: true }).click();
    await expect(page.getByRole("button", { name: "Cancel deletion" })).toBeFocused();
    await checkpoint(page, info, "confirm-crew-track-removal");
    await page.getByRole("button", { name: "Cancel deletion" }).click();
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Delete track", exact: true })).toBeFocused();
    // Also verify the list control updates the list rather than leaving a stale card.
    await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Jam tracks", exact: true }).click();
    const card = page.locator(".library-card", { hasText: title });
    await card.getByRole("button", { name: "Delete track", exact: true }).click();
    await card.getByRole("button", { name: "Delete from crew", exact: true }).click();
    await expect(card).toHaveCount(0);
    await expect(page.getByText("Track deleted from this crew.", { exact: true })).toBeVisible();
    await expectNoPageOverflow(page);
    await page.goto(`/tracks/${loadSeed().trackId}`);
    await expect(page.getByRole("heading", { name: "Blue Test Engine", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Delete track", exact: true })).toHaveCount(0);
  });
});
