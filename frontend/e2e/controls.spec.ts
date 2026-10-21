import { expect, test, type Page } from "@playwright/test";
import { API, waitForMission } from "./helpers";

function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(`console: ${m.text().slice(0, 300)}`);
  });
  return errors;
}

test("composer: every mission type shows its hint", async ({ page }) => {
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
  await expect(page.getByRole("button", { name: /Use example/ })).toHaveCount(0); // removed on request
  await expect(box).toHaveValue("");
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

  // a finished mission opens on its result; the tabs switch to the agents and back
  const panes = page.getByRole("tablist", { name: "Mission view" });
  await expect(panes.getByRole("tab", { name: "Result" })).toHaveAttribute("aria-selected", "true");
  await panes.getByRole("tab", { name: "Agents at work" }).click();
  await expect(page.locator('[data-tour="mission-floor"]')).toBeVisible();
  await expect(page.getByTestId("mission-result")).toHaveCount(0);
  await page.getByRole("tab", { name: "Graph" }).click();
  await expect(page.getByRole("tab", { name: "Graph" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Robots" }).click();
  await page.getByRole("button", { name: "Replay" }).click();
  await expect(page.getByText("Recorded events at")).toBeVisible();
  await page.getByRole("button", { name: "Back to live" }).click();
  await expect(page.getByText("Recorded events at")).toBeHidden();
  await panes.getByRole("tab", { name: "Result" }).click();
  await expect(page.getByTestId("mission-result")).toBeVisible();
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
  await email.getByRole("button", { name: "Save", exact: true }).click();
  await expect(email.getByRole("button", { name: "Save", exact: true })).toBeDisabled();
  await email.getByRole("button", { name: "Send test email" }).click();
  await expect(email.getByText(/Not signed in with Google yet|Sent\./)).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Result email address")).toHaveValue("someone@example.com");
  expect(errors).toEqual([]);
});

test("recent missions: filter by type and delete one", async ({ page, request }) => {
  const errors = watchErrors(page);
  const ticket = await (
    await request.post(`${API}/missions`, { data: { task: "Create a ticket for the slow checkout", inputs: {} } })
  ).json();
  const page1 = await (
    await request.post(`${API}/missions`, {
      data: { task: "Write a blog post about robots as an HTML page", inputs: {} },
    })
  ).json();
  await waitForMission(request, ticket.id, ["completed"]);
  await waitForMission(request, page1.id, ["paused", "completed"]);

  await page.goto("/missions");
  // the blog mission is waiting for approval: its pop-up may open; "Later" closes it
  const popup = page.getByRole("dialog", { name: "Approval needed" });
  await page.waitForTimeout(1500);
  if (await popup.isVisible()) await popup.getByRole("button", { name: "Later" }).click();
  const list = page.getByRole("region", { name: "Missions" });
  await list.getByRole("radio", { name: "Tickets" }).click();
  await expect(list.getByText("Create a ticket for the slow checkout")).toBeVisible();
  await expect(list.getByText("Write a blog post about robots as an HTML page")).toHaveCount(0);
  await list.getByRole("radio", { name: "Web pages" }).click();
  const item = list.getByText("Write a blog post about robots as an HTML page");
  await expect(item).toBeVisible();

  await item.hover();
  await list.getByRole("button", { name: /Delete mission Write a blog post about robots/ }).click();
  await list.getByRole("button", { name: "Keep" }).click(); // changing your mind keeps it
  await expect(item).toBeVisible();
  await item.hover();
  await list.getByRole("button", { name: /Delete mission Write a blog post about robots/ }).click();
  await list.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(item).toHaveCount(0);
  expect((await request.get(`${API}/missions/${page1.id}`)).status()).toBe(404);
  expect((await request.get(`${API}/missions/${ticket.id}`)).status()).toBe(200);
  expect(errors).toEqual([]);
});
