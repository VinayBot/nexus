import { expect, test, type Page } from "@playwright/test";

/** Collect uncaught page errors and console errors while a test runs. */
function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(`console: ${m.text().slice(0, 300)}`);
  });
  return errors;
}

const SCREENS: [path: string, heading: RegExp][] = [
  ["/missions", /New mission/i],
  ["/graph", /Live Graph/i],
  ["/arena", /Arena/i],
  ["/approvals", /Approvals/i],
  ["/timetravel", /Time Travel/i],
  ["/chaos", /Chaos Lab/i],
  ["/agents", /Agents/i],
  ["/insights", /Insights/i],
  ["/memory", /Memory/i],
  ["/tools", /Tools/i],
  ["/learn", /How it Works/i],
  ["/settings", /Settings/i],
];

test("every screen renders without console errors", async ({ page }) => {
  const errors = watchErrors(page);
  for (const [path, heading] of SCREENS) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("landing page shows live stats and enters the command center", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "NEXUS" })).toBeVisible();
  await expect(page.getByText("Cloud spend")).toBeVisible();
  await page.getByRole("button", { name: /Enter Command Center/ }).click();
  await page.waitForURL(/\/missions/);
  await expect(page.getByText("New mission")).toBeVisible();
  expect(errors).toEqual([]);
});

test("sidebar groups, the Advanced section and active state", async ({ page }) => {
  await page.goto("/missions");
  const nav = page.getByRole("navigation", { name: "Primary" });
  await expect(nav.getByRole("link", { name: "Missions" })).toHaveAttribute("aria-current", "page");
  await expect(nav.getByRole("link", { name: "Memory" })).toHaveCount(0);
  await nav.getByRole("button", { name: /Advanced/ }).click();
  await nav.getByRole("link", { name: "Memory" }).click();
  await page.waitForURL(/\/memory$/);
  await expect(nav.getByRole("link", { name: "Memory" })).toHaveAttribute("aria-current", "page");
});

test("insights and how-it-works tabs switch and keep the tab in the URL", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/insights");
  await expect(page.getByRole("tab", { name: "Observatory" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Benchmarks" }).click();
  await page.waitForURL(/tab=benchmarks/);
  await expect(page.getByRole("tab", { name: "Benchmarks" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Under the Hood" }).click();
  await page.waitForURL(/tab=lab/);
  await page.goto("/learn?tab=curriculum");
  await expect(page.getByRole("tab", { name: "Curriculum Map" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator('[data-tour="curriculum"]')).toBeVisible();
  expect(errors).toEqual([]);
});

test("display settings popover switches theme and performance mode", async ({ page }) => {
  await page.goto("/missions");
  await page.getByRole("button", { name: "Display settings" }).click();
  await page.getByRole("switch", { name: /Night theme/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "night");
  await page.getByRole("switch", { name: /Performance mode/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-perf", "on");
  // restore defaults for the other tests (preferences persist in localStorage)
  await page.getByRole("switch", { name: /Night theme/ }).click();
  await page.getByRole("switch", { name: /Performance mode/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "sunset");
});

test("command palette opens with the keyboard and navigates", async ({ page }) => {
  await page.goto("/missions");
  await page.keyboard.press("ControlOrMeta+k");
  const input = page.getByPlaceholder("Type a command or ask Nova…");
  await expect(input).toBeVisible();
  await input.fill("Agents");
  await page.keyboard.press("Enter");
  await page.waitForURL(/\/agents$/);
});

test("agents roster shows the whole squad", async ({ page }) => {
  await page.goto("/agents");
  for (const name of ["Commander", "Sage", "Forge", "Aegis", "Blaze", "Volt", "Frost", "Hawk", "Nova"]) {
    await expect(page.getByRole("button", { name: new RegExp(`^${name}: show spec`) })).toBeVisible();
  }
});
