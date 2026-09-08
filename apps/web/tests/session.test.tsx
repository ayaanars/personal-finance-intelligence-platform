import { render, screen, waitFor, act } from "@testing-library/react";
import { expect, it, vi, beforeEach } from "vitest";
import { SessionProvider, Protected } from "@/components/session";
import { api, ApiError } from "@/lib/api";
import { id } from "./fixtures";
const navigation = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));
const user = {
  id,
  email: "synthetic@example.com",
  workspace: { id, display_name: "Private workspace" },
};
beforeEach(() => vi.clearAllMocks());
it("does not render protected data while restoring an unknown session", () => {
  vi.spyOn(api, "me").mockReturnValue(new Promise(() => {}));
  render(
    <SessionProvider>
      <Protected>
        <p>Private history</p>
      </Protected>
    </SessionProvider>,
  );
  expect(screen.queryByText("Private history")).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Opening");
});
it("redirects a signed-out user from protected routes to login", async () => {
  vi.spyOn(api, "me").mockRejectedValue(new ApiError(401, "AUTH_REQUIRED"));
  render(
    <SessionProvider>
      <Protected>
        <p>Private history</p>
      </Protected>
    </SessionProvider>,
  );
  await waitFor(() =>
    expect(navigation.replace).toHaveBeenCalledWith("/login"),
  );
  expect(screen.queryByText("Private history")).not.toBeInTheDocument();
});
it("renders authenticated content and clears it immediately on expiry", async () => {
  vi.spyOn(api, "me").mockResolvedValue(user);
  render(
    <SessionProvider>
      <Protected>
        <p>Private history</p>
      </Protected>
    </SessionProvider>,
  );
  expect(await screen.findByText("Private history")).toBeVisible();
  act(() => window.dispatchEvent(new Event("ledgerx:unauthorized")));
  expect(screen.queryByText("Private history")).not.toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("session has ended");
});
it("does not redirect transient connection errors to login", async () => {
  vi.spyOn(api, "me").mockRejectedValue(new ApiError(0, "NETWORK_ERROR"));
  render(
    <SessionProvider>
      <Protected>
        <p>Private history</p>
      </Protected>
    </SessionProvider>,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("connection");
  expect(navigation.replace).not.toHaveBeenCalled();
});
it("does not resurrect private data from a response that arrives after expiry", async () => {
  let finish!: (value: typeof user) => void;
  vi.spyOn(api, "me").mockReturnValue(new Promise(resolve => { finish = resolve; }));
  render(<SessionProvider><Protected><p>Private history</p></Protected></SessionProvider>);
  act(() => window.dispatchEvent(new Event("ledgerx:unauthorized")));
  await act(async () => finish(user));
  expect(screen.queryByText("Private history")).not.toBeInTheDocument();
  expect(navigation.replace).toHaveBeenCalledWith("/login");
});
