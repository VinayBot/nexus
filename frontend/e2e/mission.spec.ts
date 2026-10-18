import { expect, test } from "@playwright/test";
import { API, waitForMission } from "./helpers";

test("start a mission, approve the team in the pop-up, see the result", async ({ page, request }) => {
  await page.goto("/missions");
  await expect(page.getByText("SIMULATION")).toBeVisible();
  await page.getByRole("radio", { name: "Custom team" }).click();
  await page.getByLabel("What should the agents do?").fill("Summarise how reducers merge parallel updates");
  await page.getByRole("button", { name: "Start mission" }).click();
  await page.waitForURL(/\/missions\?m=/);
  const id = new URL(page.url()).searchParams.get("m")!;

  // real events arrive over the WebSocket; the pause opens the approval pop-up on this page
  const dialog = page.getByRole("dialog", { name: "Approval needed" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Approve this team?")).toBeVisible();
  await dialog.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(dialog.getByText(/Approved/)).toBeVisible();

  const done = await waitForMission(request, id, ["completed", "failed"]);
  expect(done.status).toBe("completed");
  expect(done.outcome).toBe("success");

  await page.goto(`/missions?m=${id}`);
  const result = page.getByTestId("mission-result");
  await expect(result.getByText("Completed", { exact: true })).toBeVisible();
  const audit = await (await request.get(`${API}/audit?mission_id=${id}`)).json();
  expect(audit[0].action).toBe("approval.approve");

  // re-opening a finished mission loads its history at once: no card replays an entrance animation
  await page.waitForTimeout(1000);
  await page.reload();
  const stream = page.locator('[data-tour="thought-stream"]');
  await stream.getByRole("button", { name: "All" }).click();
  await expect(stream.locator("li").nth(5)).toBeVisible();
  await expect(stream.locator("li.thought-in")).toHaveCount(0);
});

test("a blog request builds an HTML page you can open after approving it inline", async ({ page, request }) => {
  await page.goto("/missions");
  await page
    .getByLabel("What should the agents do?")
    .fill("build a html page and write an AI blog and give me the link");
  await page.getByRole("button", { name: "Start mission" }).click();
  await page.waitForURL(/\/missions\?m=/);
  const id = new URL(page.url()).searchParams.get("m")!;

  // "Later" closes the pop-up; the same decision is still available inline on the mission
  const dialog = page.getByRole("dialog", { name: "Approval needed" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Later" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("button", { name: /approvals? waiting/ })).toBeVisible();
  const inline = page.getByTestId("inline-approval");
  await expect(inline.getByText("Approve this action?")).toBeVisible();
  await expect(inline.getByText("How AI Agents Work Together").first()).toBeVisible();
  await inline.getByRole("button", { name: "Approve", exact: true }).click();

  const done = await waitForMission(request, id, ["completed", "failed"]);
  expect(done.playbook).toBe("web_builder");
  expect(done.outcome).toBe("success");

  const result = page.getByTestId("mission-result");
  await expect(result.getByRole("link", { name: "Open page" })).toBeVisible();
  await expect(result.locator("iframe")).toBeVisible();
  const href = await result.getByRole("link", { name: "Open page" }).getAttribute("href");
  const html = await (await request.get(href!)).text();
  expect(html).toContain("<h1>How AI Agents Work Together</h1>");
});
