import { expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";

export interface Seed {
  users: { admin: { username: string; password: string }; member: { username: string; password: string } };
  defaultCrewId: string;
  trackId: string;
  trackTitle: string;
  hiddenTrackId: string;
}

export function loadSeed(): Seed {
  try {
    return JSON.parse(readFileSync(new URL("../.seed.json", import.meta.url), "utf-8"));
  } catch {
    throw new Error("Missing tests/e2e/.seed.json — run `npm run seed` first (see README).");
  }
}

export async function loginAs(page: Page, username: string, password: string): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Jam tracks" })).toBeVisible();
}

export async function expectNoPageOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "page must not scroll horizontally").toBeLessThanOrEqual(1);
}

export async function expectTouchTargets(page: Page, selector: string): Promise<void> {
  const boxes = await page.locator(selector).evaluateAll((elements) =>
    elements.map((element) => {
      const rect = element.getBoundingClientRect();
      return { width: rect.width, height: rect.height };
    }),
  );
  expect(boxes.length, `expected targets for ${selector}`).toBeGreaterThan(0);
  for (const box of boxes) {
    expect(Math.min(box.width, box.height), selector).toBeGreaterThanOrEqual(40);
  }
}

export async function expectNoSeriousA11yViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).analyze();
  const blocking = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(
    blocking.map((v) => `${v.id}: ${v.description}`),
    "no critical/serious a11y violations",
  ).toEqual([]);
}
