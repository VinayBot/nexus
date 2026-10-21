import { expect, test, type Page } from "@playwright/test";
import { API, waitForMission } from "./helpers";

function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    // Playwright injects its helper into every frame; Chrome blocks it inside the
    // script-free sandboxed page preview and logs this. It is not an app error.
    if (m.type() === "error" && !m.text().includes("frame is sandboxed"))
      errors.push(`console: ${m.text().slice(0, 300)}`);
  });
  return errors;
}

test.beforeEach(async ({ request }) => {
  await request.put(`${API}/notify`, { data: { to: "me@example.com", enabled: false } });
});

test("orange (Ember) is the default theme and an older saved choice is migrated", async ({ page }) => {
  await page.goto("/missions");
  await page.evaluate(() =>
    localStorage.setItem("nexus-ui", JSON.stringify({ state: { accent: "violet" }, version: 2 })),
  );
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-accent", "ember");
  const accent = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--accent-rgb").trim(),
  );
  expect(accent).toBe("242 103 58");
});

test("prompt asks for email: hint, result card status, approval email to the owner only", async ({ page, request }) => {
  const errors = watchErrors(page);
  await page.goto("/missions");
  const box = page.getByLabel("What should the agents do?");
  await box.fill("Write an article about email marketing");
  await page.waitForTimeout(700);
  await expect(page.getByTestId("email-hint")).toHaveCount(0); // a topic, not a request

  await box.fill("Build an HTML page about robots and send the output to boss@example.com");
  await expect(page.getByTestId("email-hint")).toContainText("boss@example.com");
  await page.getByRole("button", { name: "Start mission" }).click();
  await page.waitForURL(/\/missions\?m=/);
  const id = new URL(page.url()).searchParams.get("m")!;

  const dialog = page.getByRole("dialog", { name: "Approval needed" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Approve", exact: true }).click();
  const done = await waitForMission(request, id, ["completed", "failed"]);
  expect(done.outcome).toBe("success");
  expect(done.inputs.email_to).toEqual(["boss@example.com"]);

  // the result is shown in the app, and its email status too
  await expect(page.getByTestId("mission-result")).toBeVisible();
  await expect(page.getByTestId("email-status")).toContainText("boss@example.com");

  const outbox = (await (await request.get(`${API}/outbox?limit=20`)).json()) as {
    to: string;
    subject: string;
    mission_id: string | null;
  }[];
  const mine = (Array.isArray(outbox) ? outbox : []).filter((m) => m.mission_id === id);
  expect(mine.find((m) => m.subject.startsWith("[NEXUS] Completed"))?.to).toBe("boss@example.com");
  expect(mine.find((m) => m.subject.startsWith("[NEXUS] Approval needed"))?.to).toBe("me@example.com");
  expect(errors).toEqual([]);
});

test("no email request in the prompt: result shown, nothing emailed", async ({ page, request }) => {
  await page.goto("/missions");
  await page
    .getByLabel("What should the agents do?")
    .fill("What is the difference between ReAct and Plan-and-Execute?");
  await page.getByRole("button", { name: "Start mission" }).click();
  await page.waitForURL(/\/missions\?m=/);
  const id = new URL(page.url()).searchParams.get("m")!;
  const done = await waitForMission(request, id, ["completed", "failed"]);
  expect(done.outcome).toBe("success");
  await expect(page.getByTestId("mission-result")).toBeVisible();
  await expect(page.getByTestId("email-status")).toHaveCount(0);
  const outbox = (await (await request.get(`${API}/outbox?limit=20`)).json()) as { mission_id: string | null }[];
  expect((Array.isArray(outbox) ? outbox : []).filter((m) => m.mission_id === id)).toEqual([]);
});

test("tour: every step, does not trap you, autoplay advances, Esc exits", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/missions");
  const tour = page.getByRole("dialog", { name: "Guided tour" });
  await page.getByRole("button", { name: /Present/ }).click();
  await expect(tour).toContainText("1 / 14");
  await expect(tour).toContainText("2 / 14", { timeout: 12_000 }); // autoplay moved on by itself
  for (let i = 3; i <= 14; i++) {
    await tour.getByRole("button", { name: /Next|Finish/ }).click();
    await expect(tour).toContainText(`${i} / 14`);
  }
  await expect(page).toHaveURL(/\/settings$/);
  await expect(tour.getByRole("heading", { name: "Email results" })).toBeVisible();
  // clicking elsewhere during the tour is not undone by the tour
  await page.goto("/agents");
  await page.waitForTimeout(1200);
  await expect(page).toHaveURL(/\/agents$/);
  await page.keyboard.press("Escape");
  await expect(tour).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("animations run: task box glow, progress bar, result badge, approval breathe", async ({ page, request }) => {
  await page.goto("/missions");
  const box = page.getByLabel("What should the agents do?");
  await box.click();
  await page.waitForTimeout(400); // the border fades in over 0.3 s
  const glow = await page.evaluate(() => {
    const el = document.querySelector(".focus-glow")!;
    const st = getComputedStyle(el, "::before");
    return { opacity: st.opacity, animation: st.animationName };
  });
  expect(glow.opacity).toBe("1");
  expect(glow.animation).toBe("spin-angle");

  await box.fill("Write a blog post about robots as an HTML page");
  await page.getByRole("button", { name: "Start mission" }).click();
  await page.waitForURL(/\/missions\?m=/);
  const id = new URL(page.url()).searchParams.get("m")!;
  const dialog = page.getByRole("dialog", { name: "Approval needed" });
  await expect(dialog).toBeVisible();
  expect(await dialog.evaluate((el) => getComputedStyle(el).animationName)).toBe("breathe");
  await dialog.getByRole("button", { name: "Approve", exact: true }).click();
  await waitForMission(request, id, ["completed"]);
  const fill = page.locator(".progress-fill");
  await expect(fill).toHaveClass(/is-done/);
  expect(await fill.evaluate((el) => (el as HTMLElement).style.width)).toBe("100%");
  const badge = page.locator(".result-badge").first();
  expect(await badge.evaluate((el) => getComputedStyle(el).animationName)).toBe("badge-pop");
  expect(await badge.evaluate((el) => getComputedStyle(el, "::after").animationName)).toBe("ring-burst");
});
