import { expect } from "@playwright/test";
import type { Page, TestInfo } from "@playwright/test";
import { expectNoPageOverflow } from "./helpers";

export async function checkpoint(page: Page, info: TestInfo, name: string) {
  await expectNoPageOverflow(page);
  await page.evaluate(() => document.fonts.ready);
  const path = info.outputPath(`${name}.png`);
  await page.screenshot({ path, fullPage: true, animations: "disabled" });
  await info.attach(name, { path, contentType: "image/png" });
}

export async function loginVisual(page: Page) {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
  await expect(page).toHaveScreenshot("login.png", { fullPage: true, animations: "disabled" });
}
