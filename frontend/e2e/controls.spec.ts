import { expect, test, type Page } from "@playwright/test";
import { waitForMission } from "./helpers";

function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(`console: ${m.text().slice(0, 300)}`);
  });
  return errors;
}

test("composer: every mission type shows its hint and fills its example", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/missions");
  const box = page.getByLabel("What should the agents do?");
  for (const [type, hint] of [
    ["Web page", /styled HTML page/],
    ["Question", /judge picks the best/],
    ["Fix service", /demo shop/],
    ["Build API", /FastAPI service/],
    ["New ticket", /writes a clear bug report/],
    ["Solve ticket", /Reads a ticket/],
    ["Custom team", /designs a team/],
    ["Auto", /picks the right team/],
  ] as const) {
    await page.getByRole("radio", { name: type }).click();
    await expect(page.getByRole("radio", { name: type })).toHaveAttribute("aria-checked", "true");
    await expect(page.getByText(hint)).toBeVisible();
  }
  await page.getByRole("radio", { name: "Solve ticket" }).click();
  await expect(page.getByLabel("Ticket", { exact: true })).toBeVisible();
  await page.getByRole("radio", { name: "Question" }).click();
  await page.getByRole("button", { name: /Use example/ }).click();
  await expect(box).toHaveValue(/ReAct and Plan-and-Execute/);
  expect(errors).toEqual([]);
});

test("welcome starter runs a question mission; view toggles and replay work", async ({ page, request }) => {
  const errors = watchErrors(page);
  await page.goto("/missions");
  await page.evaluate(() => localStorage.clear());
  await page.goto("/missions");
  await expect(page.getByRole("heading", { name: "What should the agents do?" })).toBeVisible();
  await page.getByRole("button", { name: /^Question/ }).click();
  await page.waitForURL(/\/missions\?m=/);
  const id = new URL(page.url()).searchParams.get("m")!;
  const done = await waitForMission(request, id, ["completed", "failed"]);
  expect(done.playbook).toBe("council_qa");
  expect(done.outcome).toBe("success");

  const result = page.getByTestId("mission-result");
  await expect(result.getByText("You asked")).toBeVisible();
  await expect(result.getByText(/ReAct interleaves/).first()).toBeVisible();
  await result.getByRole("button", { name: "How the team did it" }).click();
  await expect(result.getByText(/Three solvers competed/)).toBeVisible();

  await page.getByRole("tab", { name: "Graph" }).click();
  await expect(page.getByRole("tab", { name: "Graph" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Robots" }).click();
  await page.getByRole("button", { name: "Replay" }).click();
  await expect(page.getByText("Recorded events at")).toBeVisible();
  await page.getByRole("button", { name: "Back to live" }).click();
  await expect(page.getByText("Recorded events at")).toBeHidden();
  expect(errors).toEqual([]);
});

test("approvals tabs, model picker, and advanced navigation", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/approvals");
  await page.getByRole("tab", { name: "Audit log" }).click();
  await expect(page.getByRole("tab", { name: "Audit log" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: /Pending/ }).click();

  await page.goto("/settings");
  const models = page.getByRole("region", { name: "Models" });
  for (const label of ["Lite", "Balanced", "Standard (7B)"])
    await expect(models.getByText(label, { exact: true })).toBeVisible();
  await expect(models.getByText("Active")).toBeVisible();

  const nav = page.getByRole("navigation", { name: "Primary" });
  await nav.getByRole("button", { name: /Advanced/ }).click();
  for (const [label, heading] of [
    ["Chaos Lab", /Chaos Lab/],
    ["Tools", /Tools/],
    ["How it Works", /How it Works/],
  ] as const) {
    await nav.getByRole("link", { name: label }).click();
    await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("settings: accent colour, model switch and email results", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("/settings");

  await page.getByRole("radio", { name: "Teal" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-accent", "teal");
  await page.getByRole("radio", { name: "Ember" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-accent", "ember");

  const balanced = page.getByTestId("profile-balanced");
  await balanced.getByRole("button", { name: "Switch to Balanced" }).click();
  await expect(balanced.getByText("Active")).toBeVisible();
  const lite = page.getByTestId("profile-lite");
  await lite.getByRole("button", { name: "Switch to Lite" }).click();
  await expect(lite.getByText("Active")).toBeVisible();

  const email = page.getByRole("region", { name: "Email results" });
  await email.getByLabel("Result email address").fill("someone@example.com");
  await email.getByRole("button", { name: "Save" }).click();
  await expect(email.getByRole("button", { name: "Save" })).toBeDisabled();
  await email.getByRole("button", { name: "Send test email" }).click();
  await expect(email.getByText(/Could not reach the mail server|Sent\./)).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Result email address")).toHaveValue("someone@example.com");
  expect(errors).toEqual([]);
});
