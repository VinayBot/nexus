import { expect, test } from "@playwright/test";

test("Nova navigates the app on request", async ({ page }) => {
  await page.goto("/missions");
  await page.getByRole("button", { name: "Ask Nova the guide" }).click();
  await page.getByLabel("Message Nova").fill("Show me the tools");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await page.waitForURL(/\/tools$/);
  await expect(page.getByRole("heading", { name: /Tools/ })).toBeVisible();
  await expect(page.getByText(/simulation mode/i)).toBeVisible();
});
