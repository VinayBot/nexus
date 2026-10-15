import { expect, test } from "@playwright/test";
import { API, waitForMission } from "./helpers";

test("start a mission, watch events, approve it, see it complete", async ({ page, request }) => {
  await page.goto("/dojo");
  await expect(page.getByText("SIMULATION")).toBeVisible();
  await page.getByRole("combobox").nth(1).selectOption("dynamic");
  await page.getByLabel("Task").fill("Summarise how reducers merge parallel updates");
  await page.getByRole("button", { name: "Begin mission" }).click();
  await page.waitForURL(/\/dojo\?m=/);
  const id = new URL(page.url()).searchParams.get("m")!;

  // real events arrive over the WebSocket and the mission pauses for team approval
  await expect(page.getByRole("link", { name: /Awaiting your seal/ })).toBeVisible();
  await expect(
    page.getByTestId("thought-stream").or(page.locator('[data-tour="thought-stream"]')).getByText("Plan r0").first(),
  ).toBeVisible();

  await page.getByRole("link", { name: /Awaiting your seal/ }).click();
  await expect(page.getByText("Team approval")).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: true }).click();

  const done = await waitForMission(request, id, ["completed", "failed"]);
  expect(done.status).toBe("completed");
  expect(done.outcome).toBe("success");

  await page.goto(`/dojo?m=${id}`);
  await expect(page.getByRole("group").getByText("Report", { exact: true })).toBeVisible();
  await expect(page.getByText("Mission completed successfully.").first()).toBeVisible();
  const audit = await (await request.get(`${API}/audit?mission_id=${id}`)).json();
  expect(audit[0].action).toBe("approval.approve");
});
