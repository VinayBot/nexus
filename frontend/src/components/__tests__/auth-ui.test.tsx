import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RoleGate } from "@/components/layout/RoleGate";
import { UserMenu } from "@/components/layout/UserMenu";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

/** Answer /auth/me with this account; record every other request. */
function backend(me: Record<string, unknown>) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${new URL(url).pathname}`);
      if (url.endsWith("/auth/me")) return Promise.resolve(Response.json(me));
      return Promise.resolve(new Response(null, { status: 204 }));
    }),
  );
  return calls;
}

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const owner = {
  username: "olga",
  role: "owner",
  auth_enabled: true,
  tokens_today: 1_900_000,
  daily_token_quota: 2_000_000,
};

describe("RoleGate", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("disables controls and explains why for a lower role", async () => {
    backend({ ...owner, role: "viewer" });
    wrap(
      <RoleGate min="operator">
        <button type="button">Start mission</button>
      </RoleGate>,
    );
    expect(await screen.findByText(/Read-only for your role/)).toHaveTextContent("Operator");
    expect(screen.getByRole("button", { name: "Start mission" })).toBeDisabled();
  });

  it("leaves controls usable for a high enough role", async () => {
    backend(owner);
    wrap(
      <RoleGate min="operator">
        <button type="button">Start mission</button>
      </RoleGate>,
    );
    await waitFor(() => expect(screen.getByRole("button", { name: "Start mission" })).toBeEnabled());
    expect(screen.queryByText(/Read-only for your role/)).toBeNull();
  });
});

describe("UserMenu", () => {
  beforeEach(() => {
    localStorage.clear();
    replace.mockClear();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("shows the account, role and today's token use", async () => {
    backend(owner);
    wrap(<UserMenu />);
    await userEvent.click(await screen.findByRole("button", { name: "Account: olga" }));
    expect(screen.getByText("Role: Owner")).toBeInTheDocument();
    expect(screen.getByLabelText("Tokens used today")).toHaveTextContent("1,900,000 / 2,000,000");
  });

  it("signs out on the server, which revokes the session and clears the cookie", async () => {
    const calls = backend(owner);
    wrap(<UserMenu />);
    await userEvent.click(await screen.findByRole("button", { name: "Account: olga" }));
    await userEvent.click(screen.getByRole("button", { name: /Sign out/ }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(calls).toContain("POST /api/v1/auth/logout");
  });

  it("is hidden when accounts are switched off", async () => {
    backend({ ...owner, auth_enabled: false });
    const { container } = wrap(<UserMenu />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
