import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import LoginPage from "@/app/login/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/layout/StudioBackdrop", () => ({ StudioBackdrop: () => null }));

function page(status: { auth_enabled: boolean; setup_required: boolean }, login?: Response) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(url.endsWith("/auth/status") ? Response.json(status) : (login ?? Response.json({}))),
    ),
  );
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <LoginPage />
    </QueryClientProvider>,
  );
}

describe("sign-in page", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("first run: creates the owner only when the passwords match", async () => {
    page({ auth_enabled: true, setup_required: true });
    expect(await screen.findByRole("heading", { name: "Create the owner account" })).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: /Create account and sign in/ });
    await userEvent.type(screen.getByLabelText("Username"), "olga");
    await userEvent.type(screen.getByLabelText("Password"), "pw-123456");
    await userEvent.type(screen.getByLabelText("Repeat the password"), "pw-999999");
    expect(screen.getByText("The passwords do not match.")).toBeInTheDocument();
    expect(submit).toBeDisabled();
    await userEvent.clear(screen.getByLabelText("Repeat the password"));
    await userEvent.type(screen.getByLabelText("Repeat the password"), "pw-123456");
    expect(submit).toBeEnabled();
  });

  it("shows the server's reason when sign-in is refused", async () => {
    page(
      { auth_enabled: true, setup_required: false },
      Response.json({ detail: "Too many sign-in attempts. Wait a minute and try again." }, { status: 429 }),
    );
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    await userEvent.type(await screen.findByLabelText("Username"), "olga");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-pass");
    await userEvent.click(screen.getByRole("button", { name: /Sign in/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many sign-in attempts");
  });
});
