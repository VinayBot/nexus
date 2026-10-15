import type { APIRequestContext } from "@playwright/test";

export const API = "http://127.0.0.1:8011/api/v1";

export async function waitForMission(request: APIRequestContext, id: string, statuses: string[], ms = 90_000) {
  const end = Date.now() + ms;
  for (;;) {
    const m = await (await request.get(`${API}/missions/${id}`)).json();
    if (statuses.includes(m.status)) return m;
    if (Date.now() > end) throw new Error(`mission ${id} stuck in ${m.status}`);
    await new Promise((r) => setTimeout(r, 500));
  }
}
