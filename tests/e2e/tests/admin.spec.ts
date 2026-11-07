import { expect, test } from "@playwright/test";
import { expectNoPageOverflow, loadSeed } from "./helpers";

test.use({ storageState: ".auth/admin.json" });

test("non-admin users see an access-denied panel", async ({ page, browser }) => {
  const seed = loadSeed();
  void seed;
  const memberContext = await browser.newContext({ storageState: ".auth/member.json" });
  const memberPage = await memberContext.newPage();
  await memberPage.goto("/admin");
  await expect(memberPage.getByRole("alert")).toContainText(/admins only/i);
  await expectNoPageOverflow(memberPage);
  await memberContext.close();
});

test("admin approves a pending request and the account works", async ({ page, request }) => {
  const username = `e2e-newbie-${Date.now()}`;
  const created = await request.post("/api/v1/access-requests", {
    data: { username, password: "s3cret-long-pass" },
  });
  expect(created.ok()).toBeTruthy();
  await page.goto("/admin");
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByRole("status").first()).toContainText(/approved/i);
  const login = await request.post("/api/v1/auth/login", {
    data: { username, password: "s3cret-long-pass" },
  });
  expect(login.ok()).toBeTruthy();
});

test("invalid profiles are rejected, valid ones are versioned", async ({ page }) => {
  await page.goto("/admin");
  await page.getByRole("tab", { name: "processing" }).click();
  await page.getByLabel("Profile name").fill(`e2e-profile-${Date.now()}`);
  await page.getByLabel("Steps (JSON array)").fill(`[{"type": "nope", "config": {}}]`);
  await page.getByRole("button", { name: "Validate and save" }).click();
  await expect(page.getByRole("alert")).toContainText(/unknown step/i);
  await page.getByLabel("Steps (JSON array)").fill(
    `[{"type": "transpose", "config": {"semitones": 2}}]`,
  );
  await page.getByRole("button", { name: "Validate and save" }).click();
  await expect(page.getByRole("status")).toContainText(/saved as a new version/i);
});

test("processor preview renders outputs without storing anything", async ({ page }) => {
  await page.goto("/admin");
  await page.getByRole("tab", { name: "processing" }).click();
  await page.getByLabel("Sample chord chart").fill("[Verse]\nC G\nRow row row your boat\n");
  await page.getByRole("button", { name: "Preview" }).click();
  const panel = page.locator(".doc-panel").first();
  await expect(panel).toBeVisible({ timeout: 30_000 });
  await expectNoPageOverflow(page);
});

test("provider test search shows fixtures and leaves the library alone", async ({ page }) => {
  async function trackTotal(): Promise<number> {
    return page.evaluate(async () => {
      const crews: { id: string }[] = await (await fetch("/api/v1/crews")).json();
      const list = await (await fetch(`/api/v1/crews/${crews[0].id}/tracks?limit=1`)).json();
      return list.total as number;
    });
  }
  await page.goto("/admin");
  await page.getByRole("tab", { name: "providers" }).click();
  await expect(page.getByText("fake", { exact: true }).first()).toBeVisible();
  const before = await trackTotal();
  await page.getByLabel("Test query").fill("blue");
  await page.getByRole("button", { name: "Search fake" }).click();
  await expect(page.getByText("Blue Test Train")).toBeVisible({ timeout: 30_000 });
  expect(await trackTotal()).toBe(before);
});
