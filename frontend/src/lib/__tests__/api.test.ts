import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, errorMessage } from "../api";
import { authHeaders, clearToken, getToken, setToken, withToken } from "../auth";

function reply(status: number, body: unknown, headers: Record<string, string> = {}) {
  return vi.fn().mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json", ...headers },
    }),
  );
}

describe("session helpers", () => {
  beforeEach(() => localStorage.clear());

  it("stores the token and sends it as a bearer header", () => {
    expect(authHeaders()).toEqual({});
    setToken("abc");
    expect(getToken()).toBe("abc");
    expect(authHeaders()).toEqual({ Authorization: "Bearer abc" });
    clearToken();
    expect(getToken()).toBeNull();
  });

  it("adds the token to links and sockets, which cannot send headers", () => {
    expect(withToken("/x")).toBe("/x");
    setToken("a b");
    expect(withToken("/x")).toBe("/x?token=a%20b");
    expect(withToken("/x?y=1")).toBe("/x?y=1&token=a%20b");
  });
});

describe("api client", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  it("sends JSON with the session and parses the reply", async () => {
    setToken("t1");
    const fetchMock = reply(200, { ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await expect(api("/things", { method: "POST", json: { a: 1 } })).resolves.toEqual({ ok: true });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.headers).toMatchObject({ Authorization: "Bearer t1", "content-type": "application/json" });
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
    setToken("expired");
    const seen = vi.fn();
    window.addEventListener("nexus:unauthorized", seen);
    vi.stubGlobal("fetch", reply(401, { detail: "Sign in" }));
    await api("/missions").catch(() => undefined);
    expect(getToken()).toBeNull();
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
