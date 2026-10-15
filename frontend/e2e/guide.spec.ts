import { expect, test } from "@playwright/test";

test("Hikari navigates the app on request", async ({ page }) => {
  await page.goto("/dojo");
  await page.getByRole("button", { name: "Ask Hikari the guide" }).click();
  await page.getByLabel("Message Hikari").fill("Show me the armory");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await page.waitForURL(/\/armory$/);
  await expect(page.getByRole("heading", { name: /Armory/ })).toBeVisible();
  await expect(page.getByText(/simulation mode/i)).toBeVisible();
});
