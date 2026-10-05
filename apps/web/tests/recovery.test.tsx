import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { PasswordRecovery } from "@/components/password-recovery";
import { api, ApiError } from "@/lib/api";

const mocks = vi.hoisted(() => ({ refresh: vi.fn(), announce: vi.fn() }));
vi.mock("@/components/session", () => ({
  useSession: () => ({ refresh: mocks.refresh }),
  announceSessionChange: mocks.announce,
}));
beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/");
});

it("requests recovery without displaying a token or account existence", async () => {
  const request = vi.spyOn(api, "requestReset").mockResolvedValue({
    message: "If the account exists, a reset link will be sent. Check your inbox.",
  });
  render(<PasswordRecovery />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Email address"), "synthetic@example.com");
  await user.click(screen.getByRole("button", { name: "Send reset link" }));
  expect(request).toHaveBeenCalledWith("synthetic@example.com");
  expect(await screen.findByRole("status")).toHaveTextContent("If the account exists");
});

it("removes the fragment and clears the password after resetting the session", async () => {
  const token = "x".repeat(43);
  window.history.replaceState(null, "", "/reset-password#token=" + token);
  const complete = vi.spyOn(api, "completeReset").mockResolvedValue(undefined);
  render(<PasswordRecovery complete />);
  expect(window.location.hash).toBe("");
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("New password"), "replacement synthetic password");
  await user.click(screen.getByRole("button", { name: "Update password" }));
  await waitFor(() => expect(mocks.refresh).toHaveBeenCalledOnce());
  expect(complete).toHaveBeenCalledWith(token, "replacement synthetic password");
  expect(mocks.announce).toHaveBeenCalledOnce();
  expect(await screen.findByRole("status")).toHaveTextContent("All previous sessions are signed out");
  expect(screen.queryByLabelText("New password")).not.toBeInTheDocument();
});

it("shows a safe used or expired token error", async () => {
  window.history.replaceState(null, "", "/reset-password#token=" + "x".repeat(43));
  vi.spyOn(api, "completeReset").mockRejectedValue(new ApiError(400, "RESET_INVALID"));
  render(<PasswordRecovery complete />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("New password"), "replacement synthetic password");
  await user.click(screen.getByRole("button", { name: "Update password" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("expired or already used");
  expect(mocks.announce).not.toHaveBeenCalled();
});
