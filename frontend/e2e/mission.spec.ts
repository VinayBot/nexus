import { expect, test } from "@playwright/test";
import { API, waitForMission } from "./helpers";

test("start a mission, watch events, approve it, see it complete", async ({ page, request }) => {
  await page.goto("/missions");
  await expect(page.getByText("SIMULATION")).toBeVisible();
  await page.getByRole("combobox").nth(1).selectOption("dynamic");
  await page.getByLabel("Task").fill("Summarise how reducers merge parallel updates");
  await page.getByRole("button", { name: "Begin mission" }).click();
  await page.waitForURL(/\/missions\?m=/);
  const id = new URL(page.url()).searchParams.get("m")!;

  // real events arrive over the WebSocket and the mission pauses for team approval
  await expect(page.getByRole("link", { name: /Awaiting your approval/ })).toBeVisible();
  await expect(
    page.getByTestId("thought-stream").or(page.locator('[data-tour="thought-stream"]')).getByText("Plan r0").first(),
  ).toBeVisible();

  await page.getByRole("link", { name: /Awaiting your approval/ }).click();
  await expect(page.getByText("Team approval")).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: true }).click();

  const done = await waitForMission(request, id, ["completed", "failed"]);
  expect(done.status).toBe("completed");
  expect(done.outcome).toBe("success");

  await page.goto(`/missions?m=${id}`);
  await expect(page.getByRole("group").getByText("Report", { exact: true })).toBeVisible();
  await expect(page.getByText("Mission completed successfully.").first()).toBeVisible();
  const audit = await (await request.get(`${API}/audit?mission_id=${id}`)).json();
  expect(audit[0].action).toBe("approval.approve");

  // re-opening a finished mission loads its history at once: no card replays an entrance animation
  await page.waitForTimeout(1000);
  await page.reload();
  const stream = page.locator('[data-tour="thought-stream"]');
  await expect(stream.locator("li").nth(5)).toBeVisible();
  await expect(stream.locator("li.thought-in")).toHaveCount(0);
});
