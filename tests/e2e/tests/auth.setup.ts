import { test as setup } from "@playwright/test";
import { readFileSync } from "node:fs";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

interface Seed {
  users: { admin: { username: string; password: string }; member: { username: string; password: string } };
}

function loadSeed(): Seed {
  return JSON.parse(readFileSync(new URL("../.seed.json", import.meta.url), "utf-8"));
}

async function apiLogin(username: string, password: string): Promise<{ cookie: string; csrf: string }> {
  const response = await fetch(`${BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) throw new Error(`seed login failed for ${username}: ${response.status}`);
  const setCookie = response.headers.get("set-cookie") ?? "";
  const cookie = setCookie.split(";")[0];
  const body = (await response.json()) as { csrf_token: string };
  return { cookie, csrf: body.csrf_token };
}

setup("authenticate as member and admin", async ({ page }) => {
  const seed = loadSeed();
  // Member session: reused by track/crew specs (fewer logins, no throttle noise).
  await page.goto("/login");
  await page.getByLabel("Username").fill(seed.users.member.username);
  await page.getByLabel("Password").fill(seed.users.member.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("heading", { name: "Jam tracks" }).waitFor();
  await page.context().storageState({ path: ".auth/member.json" });

  // Admin session: used by future admin-panel specs (S14).
  // Clear cookies client-side only: signing out would revoke the session
  // server-side and invalidate the saved member state above.
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel("Username").fill(seed.users.admin.username);
  await page.getByLabel("Password").fill(seed.users.admin.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("heading", { name: "Jam tracks" }).waitFor();
  await page.context().storageState({ path: ".auth/admin.json" });
});
