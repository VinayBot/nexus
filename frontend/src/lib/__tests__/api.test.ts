import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, errorMessage } from "../api";
import { forgetLegacyToken } from "../auth";
import { apiBase } from "../config";

function reply(status: number, body: unknown, headers: Record<string, string> = {}) {
  return vi.fn().mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json", ...headers },
    }),
  );
}

describe("session plumbing", () => {
  it("puts the API on the page's own site, so the SameSite cookie is sent", () => {
    expect(apiBase("http://127.0.0.1:8000", "localhost")).toBe("http://localhost:8000");
    expect(apiBase("http://localhost:8000", "127.0.0.1")).toBe("http://127.0.0.1:8000");
    expect(apiBase(undefined, null)).toBe("http://127.0.0.1:8000");
    // a real host is left alone
    expect(apiBase("https://api.example.com", "localhost")).toBe("https://api.example.com");
  });

  it("removes a token left in localStorage by earlier versions", () => {
    localStorage.setItem("nexus-token", "old");
    forgetLegacyToken();
    expect(localStorage.getItem("nexus-token")).toBeNull();
  });
});

describe("api client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends JSON with the session cookie and parses the reply", async () => {
    const fetchMock = reply(200, { ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await expect(api("/things", { method: "POST", json: { a: 1 } })).resolves.toEqual({ ok: true });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.credentials).toBe("include");
    expect(init.headers).toMatchObject({ "content-type": "application/json" });
    expect(init.headers).not.toHaveProperty("Authorization"); // no token in page scripts
    expect(init.body).toBe('{"a":1}');
  });

  it("turns errors into ApiError with the message and request id", async () => {
    vi.stubGlobal("fetch", reply(429, { detail: "Too many missions", request_id: "rid-1" }));
    const err = await api("/missions").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(429);
    expect((err as ApiError).message).toBe("Too many missions");
    expect((err as ApiError).requestId).toBe("rid-1");
  });

  it("signs out on 401 outside the auth routes", async () => {
    const seen = vi.fn();
    window.addEventListener("nexus:unauthorized", seen);
    vi.stubGlobal("fetch", reply(401, { detail: "Sign in" }));
    await api("/missions").catch(() => undefined);
    expect(seen).toHaveBeenCalledOnce();
    window.removeEventListener("nexus:unauthorized", seen);
  });

  it("returns undefined for 204", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(api("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });
});

describe("errorMessage", () => {
  it("reads FastAPI validation lists instead of printing [object Object]", () => {
    const body = { detail: [{ loc: ["body", "task"], msg: "String should have at least 3 characters" }] };
    expect(errorMessage(body, "x")).toBe("task: String should have at least 3 characters");
  });

  it("falls back when there is no detail", () => {
    expect(errorMessage({}, "Bad Gateway")).toBe("Bad Gateway");
    expect(errorMessage(null, "Bad Gateway")).toBe("Bad Gateway");
  });
});
