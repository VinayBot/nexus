import { expect, test } from "@playwright/test";

// signed out: no stored session and no Authorization header
test.use({ storageState: { cookies: [], origins: [] } });

test("sign-in page: wrong password, then the owner signs in and lands back where they were", async ({ page }) => {
  await page.goto("/approvals");
  await page.waitForURL(/\/login\?next=%2Fapprovals/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password").fill("not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Wrong username or password" })).toBeVisible();
  await page.getByLabel("Password").fill("owner-pass-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/approvals$/);
  await expect(page.getByRole("button", { name: "Account: owner" })).toBeVisible();
});

test("a viewer can look but not act", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("viewer");
  await page.getByLabel("Password").fill("viewer-pass-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/missions$/);
  await page.getByLabel("What should the agents do?").fill("What is ReAct?");
  await expect(page.getByRole("button", { name: "Start mission" })).toBeDisabled();
  await page.goto("/settings");
  await expect(page.getByText(/Read-only for your role/).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Users" })).toHaveCount(0); // owner only
  // the session is an HttpOnly cookie: page scripts cannot see it
  expect(await page.evaluate(() => localStorage.getItem("nexus-token"))).toBeNull();
  expect(await page.evaluate(() => document.cookie)).not.toContain("nexus_session");
  // the server refuses too, whatever the UI shows (same browser session, cookie only)
  const res = await page.request.post("http://127.0.0.1:8011/api/v1/missions", {
    data: { task: "hello" },
  });
  expect(res.status()).toBe(403);
});

test("the owner adds an operator, who can sign in; sign out returns to the login page", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password").fill("owner-pass-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/missions$/);
  await page.goto("/settings");
  const users = page.getByRole("region", { name: "Users" });
  await users.getByLabel("New username").fill("olivia");
  await users.getByLabel("New user password").fill("olivia-pass-123");
  await users.getByRole("radio", { name: /Operator/ }).check();
  await users.getByRole("button", { name: "Add user" }).click();
  await expect(users.getByLabel("Role of olivia")).toHaveValue("operator");

  await page.getByRole("button", { name: "Account: owner" }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL(/\/login/);
  await page.getByLabel("Username").fill("olivia");
  await page.getByLabel("Password").fill("olivia-pass-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Account: olivia" })).toBeVisible();
  await page.goto("/missions");
  await page.getByLabel("What should the agents do?").fill("What is ReAct?");
  await expect(page.getByRole("button", { name: "Start mission" })).toBeEnabled();
});
