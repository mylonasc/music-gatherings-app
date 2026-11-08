import { expect, test } from "@playwright/test";
import { checkpoint } from "./checkpoint";
import { expectNoPageOverflow, expectNoSeriousA11yViolations, loginAs } from "./helpers";

test.use({ storageState: ".auth/member.json" });

test("compact cards keep reactions independent for two users", async ({ page, browser, baseURL }, info) => {
  const title = `Compact fixture ${info.project.name}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Suggest a track", exact: true }).click();
  await page.getByLabel("Title (optional)").fill(title);
  await page.getByRole("button", { name: "Suggest", exact: true }).click();
  const own = page.locator(".library-card", { hasText: title });
  await own.getByRole("button", { name: "Give thumbs up" }).click();
  await expect(own.getByRole("button", { name: "Remove thumbs up" })).toHaveAttribute("aria-pressed", "true");
  await expect(own.getByRole("status")).toHaveText("1 thumbs up");
  await checkpoint(page, info, "compact-track-list");

  const adminContext = await browser.newContext({ baseURL, storageState: ".auth/admin.json" });
  const otherContext = await browser.newContext({ baseURL, storageState: { cookies: [], origins: [] } });
  try {
    // Both actors are members of the same crew. Admins see additional crews and
    // the library currently defaults to the first crew in their own list.
    const username = `thumbs-${info.project.name}-${Date.now()}`;
    const created = await adminContext.request.post("/api/v1/access-requests", { data: { username, password: "thumbs-test-pass-1" } });
    expect(created.ok()).toBeTruthy();
    const me = await (await adminContext.request.get("/api/v1/auth/me")).json();
    const approved = await adminContext.request.post(`/api/v1/access-requests/${(await created.json()).id}/approve`, { headers: { "X-CSRF-Token": me.csrf_token } });
    expect(approved.ok()).toBeTruthy();
    const secondMember = await otherContext.newPage();
    await loginAs(secondMember, username, "thumbs-test-pass-1");
    const other = secondMember.locator(".library-card", { hasText: title });
    await expect(other.getByRole("button", { name: "Give thumbs up" })).toHaveAttribute("aria-pressed", "false");
    await expect(other.getByRole("status")).toHaveText("1 thumbs up");
    await other.getByRole("button", { name: "Give thumbs up" }).click();
    await expect(other.getByRole("status")).toHaveText("2 thumbs up");
    await page.reload();
    await expect(own.getByRole("status")).toHaveText("2 thumbs up");
    await own.getByRole("button", { name: "Remove thumbs up" }).click();
    await expect(own.getByRole("status")).toHaveText("1 thumbs up");
    await expect(own.getByRole("button", { name: "Give thumbs up" })).toHaveAttribute("aria-pressed", "false");
    await secondMember.reload();
    await expect(other.getByRole("button", { name: "Remove thumbs up" })).toHaveAttribute("aria-pressed", "true");
    await other.getByRole("button", { name: "Remove thumbs up" }).click();
    await expect(other.getByRole("status")).toHaveText("0 thumbs up");
  } finally { await adminContext.close(); await otherContext.close(); }

  await page.setViewportSize({ width: 320, height: 568 });
  const seeded = page.locator(".library-card", { hasText: "Blue Test Engine — The Determinists" });
  await expect(seeded).toBeVisible();
  const height = await seeded.evaluate((element) => element.getBoundingClientRect().height);
  expect(height, "representative card at 320px should remain compact").toBeLessThanOrEqual(170);
  await info.attach("compact-card-layout", { body: JSON.stringify({ viewportWidth: 320, representativeCardHeight: height }), contentType: "application/json" });
  await expect(own.getByRole("button")).toHaveCount(2);
  for (const button of await own.getByRole("button").all()) {
    const box = await button.boundingBox();
    expect(box!.width).toBeGreaterThanOrEqual(44);
    expect(box!.height).toBeGreaterThanOrEqual(44);
  }
  await expectNoPageOverflow(page);
  await expectNoSeriousA11yViolations(page);
  await checkpoint(page, info, "compact-track-list-320px");
});
