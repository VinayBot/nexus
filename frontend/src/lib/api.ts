import { onUnauthorized } from "./auth";
import { API_URL } from "./config";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly body?: unknown,
    /** Matches the server log line; worth quoting in a bug report. */
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** The backend's `detail`: a message, or FastAPI's list of validation errors. */
export function errorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object" || !("detail" in body)) return fallback;
  const detail = (body as { detail: unknown }).detail;
  if (Array.isArray(detail)) {
    return (
      detail
        .map((d: { loc?: unknown[]; msg?: string }) => {
          const field = (d.loc ?? []).filter((p) => p !== "body").join(".");
          return field ? `${field}: ${d.msg ?? "invalid"}` : (d.msg ?? "invalid");
        })
        .join("; ") || fallback
    );
  }
  return typeof detail === "string" ? detail : fallback;
}

type Json = Record<string, unknown> | unknown[] | string | number | boolean | null;

/** Typed fetch against /api/v1. Throws ApiError with the backend's `detail` message. */
export async function api<T>(path: string, init: RequestInit & { json?: Json } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...rest,
    credentials: "include", // the HttpOnly session cookie
    headers: {
      ...(json !== undefined ? { "content-type": "application/json" } : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (res.status === 401 && !path.startsWith("/auth/")) onUnauthorized();
  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => undefined);
    }
    const requestId =
      (body && typeof body === "object" && "request_id" in body
        ? String((body as { request_id: unknown }).request_id)
        : null) ??
      res.headers.get("x-request-id") ??
      undefined;
    throw new ApiError(res.status, errorMessage(body, res.statusText), body, requestId);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const get = <T>(path: string) => api<T>(path);
export const post = <T>(path: string, json?: Json) => api<T>(path, { method: "POST", json: json ?? {} });
export const put = <T>(path: string, json: Json) => api<T>(path, { method: "PUT", json });
export const del = <T>(path: string) => api<T>(path, { method: "DELETE" });
