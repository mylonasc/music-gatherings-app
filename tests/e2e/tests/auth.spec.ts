import { expect, test } from "@playwright/test";
import { expectNoPageOverflow, expectNoSeriousA11yViolations, expectTouchTargets, loadSeed, loginAs } from "./helpers";

test("login lands on the jam tracks default route", async ({ page }) => {
  const seed = loadSeed();
  await loginAs(page, seed.users.member.username, seed.users.member.password);
  await expect(page).toHaveURL("/");
  await expectNoPageOverflow(page);
  await expectTouchTargets(page, "header nav a");
});

test("wrong credentials show an error and stay on login", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("nobody");
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toContainText("invalid credentials");
  await expect(page).toHaveURL(/\/login/);
  await expectNoPageOverflow(page);
});

test.describe("as signed-in member", () => {
  // Deliberately NOT using the shared member storage state: signing out
  // revokes the session server-side, which would break parallel tests.
  test("logout returns to the login screen", async ({ page }) => {
    const seed = loadSeed();
    await loginAs(page, seed.users.member.username, seed.users.member.password);
    await expect(page.getByRole("heading", { name: "Jam tracks" })).toBeVisible();
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  });
});

test("login page has no serious accessibility violations", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expectNoSeriousA11yViolations(page);
});
