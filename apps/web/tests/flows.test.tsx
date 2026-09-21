import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { api, ApiError, type Inspection } from "@/lib/api";
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
const inspection: Inspection = {
  recognition: {state:"needs_mapping", mapping:null, questions:[], evidence:[], profile_name:null},
  headers: ["Date", "Details", "Amount", "CCY"],
  suggestions: {transaction_date: "Date", description: "Details", amount: "Amount", currency: "CCY"},
  date_formats: ["YYYY-MM-DD"], profiles: [], total_rows: 1, invalid_rows: null,
  samples: [{source_row_number: 2, source: ["2026-09-01", "Synthetic", "1", "AED"], normalized: null}],
};
const checkedInspection: Inspection = {...inspection, recognition:{...inspection.recognition, state:"recognized"}, invalid_rows: 0, samples: [{...inspection.samples[0], normalized: preview.rows.items[0]}]};
it("inspects and previews before staging, retaining mapping and key across uncertain retries", async () => {
  vi.spyOn(api, "inspect").mockResolvedValueOnce(inspection).mockResolvedValue(checkedInspection);
  const upload = vi
    .spyOn(api, "upload")
    .mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR"))
    .mockResolvedValue(preview);
  vi.spyOn(api, "finalize").mockResolvedValue({id, status:"completed", accepted_rows:1, finalized_at:"2026-09-21"});
  render(<UploadStatement />);
  const user = userEvent.setup();
  await user.upload(
    screen.getByLabelText("Choose your statement"),
    new File(["synthetic csv"], "test.csv", { type: "text/csv" }),
  );
  expect(upload).not.toHaveBeenCalled();
  await user.click(await screen.findByRole("button", { name: "Preview normalized rows" }));
  await user.click(await screen.findByRole("button", { name: "Confirm import" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("retry");
  await user.click(screen.getByRole("button", { name: "Retry same upload" }));
  await waitFor(() =>
    expect(mocks.push).toHaveBeenCalledWith(`/app/import/${id}`),
  );
  expect(upload.mock.calls[0][1]).toBe(upload.mock.calls[1][1]);
  expect(upload.mock.calls[0][2]).toEqual(upload.mock.calls[1][2]);
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
  vi.spyOn(api, "inspect").mockResolvedValueOnce(inspection).mockResolvedValue(checkedInspection);
  const upload = vi
    .spyOn(api, "upload")
    .mockRejectedValueOnce(new ApiError(422, "VALIDATION_ERROR"))
    .mockResolvedValue(preview);
  vi.spyOn(api, "finalize").mockResolvedValue({id, status:"completed", accepted_rows:1, finalized_at:"2026-09-21"});
  render(<UploadStatement />);
  const user = userEvent.setup();
  await user.upload(
    screen.getByLabelText("Choose your statement"),
    new File(["bad headers"], "bad.csv", { type: "text/csv" }),
  );
  await user.click(await screen.findByRole("button", { name: "Preview normalized rows" }));
  await user.click(await screen.findByRole("button", { name: "Confirm import" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  await user.upload(
    screen.getByLabelText("Choose your statement"),
    new File(["corrected synthetic csv"], "corrected.csv", {
      type: "text/csv",
    }),
  );

  await user.click(await screen.findByRole("button", { name: "Confirm import" }));
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

it("requires ambiguous date confirmation and invalidates preview when mapping changes", async () => {
  vi.spyOn(api, "inspect").mockResolvedValueOnce({...inspection, date_formats: ["DD/MM/YYYY", "MM/DD/YYYY"]}).mockResolvedValue(checkedInspection);
  const upload = vi.spyOn(api, "upload").mockResolvedValue(preview);
  vi.spyOn(api, "finalize").mockResolvedValue({id, status:"completed", accepted_rows:1, finalized_at:"2026-09-21"});
  render(<UploadStatement />);
  const user = userEvent.setup();
  await user.upload(screen.getByLabelText("Choose your statement"), new File(["synthetic"], "test.csv"));
  expect(await screen.findByRole("button", {name: "Preview normalized rows"})).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("Date format"), "DD/MM/YYYY");
  await user.click(screen.getByRole("button", {name: "Preview normalized rows"}));
  await screen.findByRole("button", {name: "Confirm import"});
  await user.click(screen.getByRole("button", {name:"Review mapping"}));
  await user.selectOptions(screen.getByLabelText("Date format"), "MM/DD/YYYY");
  expect(screen.queryByRole("button", {name: "Confirm import"})).not.toBeInTheDocument();
  expect(upload).not.toHaveBeenCalled();
});
it("saves only a named mapping after successful mapping", async () => {
  vi.spyOn(api, "preview").mockResolvedValue({...preview, can_save_mapping: true});
  const save = vi.spyOn(api, "saveMappingProfile").mockResolvedValue({id, name: "Synthetic CSV", mapping: {transaction_date:"Date",description:"Details",amount_mode:"single",amount:"Amount",debit:null,credit:null,currency:"CCY",fixed_currency:null,date_format:"YYYY-MM-DD"}});
  render(<PreviewStatement id={id} />);
  await userEvent.type(await screen.findByLabelText("Profile name"), "Synthetic CSV");
  await userEvent.click(screen.getByRole("button", {name: "Save mapping"}));
  await screen.findByText("Mapping saved as Synthetic CSV.");
  expect(save).toHaveBeenCalledWith(id, "Synthetic CSV");
});

it("shows automatic preview without manual mapping and finalizes only on confirmation", async () => {
  const mapping = {transaction_date:"Date",description:"Details",amount_mode:"single" as const,amount:"Amount",debit:null,credit:null,currency:"CCY",fixed_currency:null,date_format:"YYYY-MM-DD" as const};
  vi.spyOn(api,"inspect").mockResolvedValue({...checkedInspection, recognition:{state:"recognized",mapping,questions:[],evidence:["Unique columns"],profile_name:"Synthetic saved profile"}});
  const upload = vi.spyOn(api,"upload").mockResolvedValue(preview);
  const finalize = vi.spyOn(api,"finalize").mockResolvedValue({id,status:"completed",accepted_rows:1,finalized_at:"2026-09-21"});
  render(<UploadStatement />);
  await userEvent.upload(screen.getByLabelText("Choose your statement"),new File(["synthetic"],"test.csv"));
  await screen.findByText("Recognized automatically");
  expect(screen.getByText(/Applied saved mapping/)).toBeVisible();
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  expect(upload).not.toHaveBeenCalled(); expect(finalize).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button",{name:"Confirm import"}));
  await waitFor(()=>expect(finalize).toHaveBeenCalledWith(id,id));
  expect(upload.mock.calls[0][2]).toEqual(mapping);
});
it("asks only for the date format when the other columns are recognized", async () => {
  vi.spyOn(api,"inspect").mockResolvedValue({...inspection, recognition:{state:"needs_confirmation",mapping:null,questions:["date_format"],evidence:[],profile_name:null},date_formats:["DD/MM/YYYY","MM/DD/YYYY"]});
  render(<UploadStatement />);
  await userEvent.upload(screen.getByLabelText("Choose your statement"),new File(["synthetic"],"test.csv"));
  expect(await screen.findByLabelText("Date format")).toHaveValue("");
  expect(screen.getAllByRole("combobox")).toHaveLength(1);
  expect(screen.queryByRole("button",{name:"Confirm import"})).not.toBeInTheDocument();
});

it("keeps the file and mapping locked when finalize fails after staging", async () => {
  vi.spyOn(api,"inspect").mockResolvedValue({...checkedInspection,recognition:{...checkedInspection.recognition,state:"recognized"}});
  const upload = vi.spyOn(api,"upload").mockResolvedValue(preview);
  const finalize = vi.spyOn(api,"finalize").mockRejectedValueOnce(new ApiError(403,"CSRF_INVALID")).mockResolvedValue({id,status:"completed",accepted_rows:1,finalized_at:"2026-09-21"});
  render(<UploadStatement />);
  await userEvent.upload(screen.getByLabelText("Choose your statement"),new File(["synthetic"],"test.csv"));
  await userEvent.click(await screen.findByRole("button",{name:"Confirm import"}));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Choose your statement")).toBeDisabled();
  await userEvent.click(screen.getByRole("button",{name:"Retry same upload"}));
  await waitFor(()=>expect(finalize).toHaveBeenCalledTimes(2));
  expect(finalize.mock.calls).toEqual([[id,id],[id,id]]);
  expect(upload.mock.calls[0][1]).toBe(upload.mock.calls[1][1]);
});
