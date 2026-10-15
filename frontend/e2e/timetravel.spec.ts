import { expect, test } from "@playwright/test";
import { API, waitForMission } from "./helpers";

test("fork a finished mission from the tournament runner-up and compare branches", async ({ page, request }) => {
  const m = await (
    await request.post(`${API}/missions`, {
      data: { task: "Compare ReAct with Plan-and-Execute", playbook: "council_qa" },
    })
  ).json();
  await waitForMission(request, m.id, ["completed"]);

  await page.goto(`/timetravel/${m.id}`);
  await expect(page.getByText("main · success")).toBeVisible();
  await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/runner-up") && r.ok()),
    page.getByRole("button", { name: /Choose the tournament runner-up/ }).click(),
  ]);
  await expect
    .poll(
      async () => {
        const h = await (await request.get(`${API}/missions/${m.id}/history`)).json();
        const mission = await (await request.get(`${API}/missions/${m.id}`)).json();
        return mission.status === "completed" ? h.branches.length : 0;
      },
      { timeout: 60_000 },
    )
    .toBe(2);
  await page.reload();
  await page.getByRole("button", { name: /⇄/ }).click();
  await expect(page.getByText(/Branch comparison/)).toBeVisible();
  await expect(page.getByRole("cell", { name: "winner" })).toBeVisible();
});
