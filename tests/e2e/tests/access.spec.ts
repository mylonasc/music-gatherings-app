import { expect, test } from "@playwright/test";
import { expectNoPageOverflow, loadSeed } from "./helpers";

test("anonymous users are sent to login", async ({ page }) => {
  const seed = loadSeed();
  await page.goto(`/tracks/${seed.trackId}`);
  await expect(page).toHaveURL(/\/login\?next=/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expectNoPageOverflow(page);
});

test.describe("as crew member", () => {
  test.use({ storageState: ".auth/member.json" });

  test("members cannot see another crew's track", async ({ page }) => {
    const seed = loadSeed();
    await page.goto(`/tracks/${seed.hiddenTrackId}`);
    await expect(page.getByRole("alert")).toContainText(/not found/i);
    await expectNoPageOverflow(page);
  });
});
