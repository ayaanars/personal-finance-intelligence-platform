import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
import { AuthForm } from "@/components/auth-form";
import { Landing } from "@/components/landing";
import { UploadStatement, PreviewStatement } from "@/features/imports";
import { TransactionHistory, TransactionDetail } from "@/features/transactions";
import { Shell } from "@/components/shell";
import { id, preview, transaction } from "./fixtures";
const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  clear: vi.fn(),
  session: { user: null as { id: string } | null, loading: false, error: "" },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
  usePathname: () => "/app",
}));
vi.mock("@/components/session", () => ({
  useSession: () => ({
    ...mocks.session,
    refresh: mocks.refresh,
    clear: mocks.clear,
  }),
  announceSessionChange: vi.fn(),
}));
beforeEach(() => {
  vi.clearAllMocks();
  mocks.session = { user: null, loading: false, error: "" };
});
it("public root renders without authentication, with truthful feature disclosure", async () => {
  render(<Landing />);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    "Your money.In perspective.",
  );
  expect(
    screen.getByText(/Behavioral analysis is planned/),
  ).toBeInTheDocument();
  expect(screen.getByText("Synthetic transactions")).toBeInTheDocument();
  expect(
    screen.getAllByRole("link", { name: /Create account/ })[0],
  ).toHaveAttribute("href", "/register");
  await userEvent.click(
    screen.getByRole("button", { name: "Explore Carrefour example" }),
  );
  expect(screen.getByText("CARREFOUR MOE")).toBeInTheDocument();
  expect(mocks.replace).not.toHaveBeenCalled();
});
it("registers then logs in with the existing cookie API", async () => {
  const credentials = vi.spyOn(api, "credentials").mockResolvedValue(undefined);
  render(<AuthForm mode="register" />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Create account" }));
  expect(credentials).not.toHaveBeenCalled();
  await user.type(
    screen.getByLabelText("Email address"),
    "synthetic@example.com",
  );
  await user.type(screen.getByLabelText("Password"), "synthetic-password-long");
  await user.click(screen.getByRole("button", { name: "Create account" }));
  await waitFor(() => expect(mocks.refresh).toHaveBeenCalled());
  expect(credentials.mock.calls.map((call) => call[0])).toEqual([
    "register",
    "login",
  ]);
  expect(screen.getByLabelText("Password")).toHaveValue("");
});
it("shows failed login then restores session on successful login", async () => {
  vi.spyOn(api, "credentials")
    .mockRejectedValueOnce(new ApiError(401, "INVALID_CREDENTIALS"))
    .mockResolvedValue(undefined);
  render(<AuthForm mode="login" />);
  const user = userEvent.setup();
  await user.type(
    screen.getByLabelText("Email address"),
    "synthetic@example.com",
  );
  await user.type(screen.getByLabelText("Password"), "synthetic-password-long");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("did not match");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(mocks.refresh).toHaveBeenCalled());
});
it("redirects a successful session into the authenticated app", async () => {
  mocks.session.user = { id };
  render(<AuthForm mode="login" />);
  await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/app"));
});
it("revokes session before clearing private state and redirecting", async () => {
  const logout = vi.spyOn(api, "logout").mockResolvedValue(undefined);
  render(
    <Shell>
      <p>History</p>
    </Shell>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Log out" }));
  expect(logout).toHaveBeenCalledOnce();
  expect(mocks.clear).toHaveBeenCalledOnce();
  expect(mocks.replace).toHaveBeenCalledWith("/login");
});
it("uploads only on submit and retains the key across uncertain retries", async () => {
  const upload = vi
    .spyOn(api, "upload")
    .mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR"))
    .mockResolvedValue(preview);
  render(<UploadStatement />);
  const user = userEvent.setup();
  await user.upload(
    screen.getByLabelText("Drop a CSV here, or choose a file"),
    new File(["synthetic csv"], "test.csv", { type: "text/csv" }),
  );
  expect(upload).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Review statement" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("retry");
  await user.click(screen.getByRole("button", { name: "Retry same upload" }));
  await waitFor(() =>
    expect(mocks.push).toHaveBeenCalledWith(`/app/import/${id}`),
  );
  expect(upload.mock.calls[0][1]).toBe(upload.mock.calls[1][1]);
});
it("blocks the whole invalid import and shows row reasons", async () => {
  vi.spyOn(api, "preview").mockResolvedValue({
    ...preview,
    status: "invalid",
    can_finalize: false,
    valid_rows: 0,
    invalid_rows: 1,
    rows: {
      ...preview.rows,
      items: [
        {
          ...preview.rows.items[0],
          errors: [{ code: "AMOUNT", message: "Amount must be nonzero" }],
        },
      ],
    },
  });
  render(<PreviewStatement id={id} />);
  expect(await screen.findByText("Amount must be nonzero")).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent(
    "whole import is blocked",
  );
  expect(
    screen.queryByRole("button", { name: "Finalize import" }),
  ).not.toBeInTheDocument();
});
it("requires explicit finalization and then offers transaction history", async () => {
  vi.spyOn(api, "preview")
    .mockResolvedValueOnce(preview)
    .mockResolvedValue({
      ...preview,
      status: "completed",
      can_finalize: false,
      accepted_rows: 1,
    });
  const finalize = vi.spyOn(api, "finalize").mockResolvedValue({
    id,
    status: "completed",
    accepted_rows: 1,
    finalized_at: "2026-09-07",
  });
  render(<PreviewStatement id={id} />);
  const button = await screen.findByRole("button", { name: "Finalize import" });
  expect(finalize).not.toHaveBeenCalled();
  await userEvent.click(button);
  expect(
    await screen.findByRole("link", { name: "View transactions" }),
  ).toHaveAttribute("href", "/app/transactions");
  expect(finalize).toHaveBeenCalledWith(id, id);
});
it("renders exact money and replaces pages instead of accumulating history", async () => {
  const list = vi
    .spyOn(api, "transactions")
    .mockResolvedValueOnce({
      items: [transaction],
      page: { next_cursor: "opaque", has_more: true },
    })
    .mockResolvedValue({
      items: [{ ...transaction, id: "second", merchant: "Second merchant" }],
      page: { next_cursor: null, has_more: false },
    });
  render(<TransactionHistory />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading");
  expect(await screen.findByText("−48.50 AED")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Next page/ }));
  expect(await screen.findByText("Second merchant")).toBeInTheDocument();
  expect(screen.queryByText("Talabat")).not.toBeInTheDocument();
  expect(list).toHaveBeenLastCalledWith("opaque");
});
it("offers actionable empty and network states", async () => {
  vi.spyOn(api, "transactions")
    .mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR"))
    .mockResolvedValue({
      items: [],
      page: { next_cursor: null, has_more: false },
    });
  render(<TransactionHistory />);
  expect(await screen.findByRole("alert")).toHaveTextContent("connection");
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(
    await screen.findByText("Your story starts here."),
  ).toBeInTheDocument();
});
it("saves a category from the server response", async () => {
  vi.spyOn(api, "transaction").mockResolvedValue(transaction);
  const save = vi.spyOn(api, "category").mockResolvedValue({
    ...transaction,
    category: "Education",
    version: 2,
    categorization_source: "manual",
  });
  render(<TransactionDetail id={id} />);
  await userEvent.selectOptions(
    await screen.findByLabelText("Category"),
    "Education",
  );
  await userEvent.click(screen.getByRole("button", { name: "Save category" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Category saved");
  expect(save).toHaveBeenCalledWith(transaction, "Education", "keep");
});
it("refetches conflicts before allowing another save", async () => {
  const read = vi
    .spyOn(api, "transaction")
    .mockResolvedValueOnce(transaction)
    .mockResolvedValue({
      ...transaction,
      category: "Travel",
      categorization_source: "manual",
      version: 2,
    });
  const save = vi
    .spyOn(api, "category")
    .mockRejectedValue(new ApiError(409, "VERSION_CONFLICT"));
  render(<TransactionDetail id={id} />);
  await userEvent.selectOptions(
    await screen.findByLabelText("Category"),
    "Education",
  );
  await userEvent.click(screen.getByRole("button", { name: "Save category" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "changed elsewhere",
  );
  await waitFor(() =>
    expect(screen.getByLabelText("Category")).toHaveValue("Travel"),
  );
  expect(read).toHaveBeenCalledTimes(2);
  expect(save).toHaveBeenCalledOnce();
});
it("allows replacing a CSV rejected by the parser without retrying different bytes under the same key", async () => {
  const upload = vi
    .spyOn(api, "upload")
    .mockRejectedValueOnce(new ApiError(422, "VALIDATION_ERROR"))
    .mockResolvedValue(preview);
  render(<UploadStatement />);
  const user = userEvent.setup();
  await user.upload(
    screen.getByLabelText("Drop a CSV here, or choose a file"),
    new File(["bad headers"], "bad.csv", { type: "text/csv" }),
  );
  await user.click(screen.getByRole("button", { name: "Review statement" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  await user.upload(
    screen.getByLabelText("bad.csv"),
    new File(["corrected synthetic csv"], "corrected.csv", {
      type: "text/csv",
    }),
  );
  await user.click(screen.getByRole("button", { name: "Review statement" }));
  await waitFor(() => expect(upload).toHaveBeenCalledTimes(2));
  expect(upload.mock.calls[0][1]).not.toBe(upload.mock.calls[1][1]);
});

it("submits browser-autofilled values even without React change events", async () => {
  const credentials = vi.spyOn(api, "credentials").mockResolvedValue(undefined);
  render(<AuthForm mode="login" />);
  (screen.getByLabelText("Email address") as HTMLInputElement).value =
    "autofill@example.com";
  (screen.getByLabelText("Password") as HTMLInputElement).value =
    "synthetic-autofilled-password";
  await userEvent.click(
    screen.getByRole("button", { name: "Sign in" }),
  );
  expect(credentials).toHaveBeenCalledWith(
    "login",
    "autofill@example.com",
    "synthetic-autofilled-password",
  );
});

it("remembers and removes a merchant preference only when requested", async () => {
  const known = { ...transaction, merchant_code: "talabat", merchant_source: "catalog_alias" };
  vi.spyOn(api, "transaction").mockResolvedValue(known);
  const save = vi.spyOn(api, "category").mockResolvedValue({ ...known, category: "Education", version: 2, categorization_source: "manual" });
  render(<TransactionDetail id={id} />);
  await userEvent.selectOptions(await screen.findByLabelText("Category"), "Education");
  const preference = screen.getByLabelText("Future Talabat transactions");
  expect(preference).toHaveValue("keep");
  await userEvent.selectOptions(preference, "save");
  await userEvent.click(screen.getByRole("button", { name: "Save category" }));
  await waitFor(() => expect(save).toHaveBeenCalledWith(known, "Education", "save"));
  await waitFor(() => expect(preference).toHaveValue("keep"));
  await userEvent.selectOptions(preference, "forget");
  await userEvent.click(screen.getByRole("button", { name: "Save category" }));
  await waitFor(() => expect(save.mock.calls[1][2]).toBe("forget"));
});

it("refreshes automatic metadata without clearing the selected correction", async () => {
  const corrected = { ...transaction, category: "Travel" as const, categorization_source: "manual" };
  vi.spyOn(api, "transaction").mockResolvedValue(corrected);
  const refresh = vi.spyOn(api, "reprocess").mockResolvedValue({ ...corrected, version: 2 });
  render(<TransactionDetail id={id} />);
  await screen.findByLabelText("Category");
  await userEvent.click(screen.getByText("Why this automatic category?"));
  await userEvent.click(screen.getByRole("button", { name: "Refresh automatic details" }));
  await waitFor(() => expect(refresh).toHaveBeenCalledWith(corrected));
  expect(screen.getByLabelText("Category")).toHaveValue("Travel");
  expect(await screen.findByRole("status")).toHaveTextContent("corrections are preserved");
});
