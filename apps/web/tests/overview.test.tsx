import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { Overview } from "@/features/overview";
import { Shell } from "@/components/shell";
import { api, ApiError } from "@/lib/api";
import { intelligenceSchema as overviewSchema, type IntelligenceData as OverviewData } from "@/lib/analytics";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }), usePathname: () => "/app" }));
const totals = {
  income: "2000.0000", inflows: "2025.0000", other_inflows: "25.0000", outflow: "500.0000",
  net_cash_flow: "1525.0000", spending: "250.0000", cash_out: "50.0000", transfers_out: "200.0000", transaction_count: 5,
};
const data: OverviewData = {
  month: "2026-09", available_months: ["2026-09", "2026-08"], window_start: "2026-04",
  methodology_version: "intelligence-v1", intelligence_version: "longitudinal-v1", coverage_note: "Based on imported activity; months may be partial.",
  currencies: [{
    currency: "AED", totals, observed_start: "2026-09-01", observed_end: "2026-09-05",
    baselines: { prior_months: [], observed_months: 2, categories: [], method: "Three prior months required.",
      metrics: ["Spending", "Outflow", "Income"].map((name) => ({
        name, kind: "metric" as const, state: "insufficient_history" as const, current: "250.0000",
        mean: null, low: null, high: null, average_three: null, average_six: null, delta: null,
        relative_percent: null, position: null, current_scale: null, low_scale: null, high_scale: null,
        mean_scale: null, months: [], values: [],
      })),
    },
    recurring: {state: "insufficient_history", payments: [], candidates: [], monthly_estimate: "0.0000", annual_estimate: "0.0000", matched_spending: "0.0000", other_spending: "250.0000", matched_share_percent: "0.00", method: "Likely patterns, not confirmed subscriptions."},
    behaviour: {
      spending_count: 1, average_purchase: "250.0000", active_spending_days: 1,
      weekday_weekend: ["Monday-Friday", "Saturday-Sunday"].map((name) => ({ name, amount: "0.0000", transaction_count: 0, share_percent: null })),
      month_parts: ["Days 1-10", "Days 11-20", "Days 21-31"].map((name) => ({ name, amount: "0.0000", transaction_count: 0, share_percent: null })),
      top_spending_merchants: [], top_five_category_share: "100.00", top_five_merchant_share: "100.00",
      largest_purchases: [], merchant_changes: [], newly_observed_merchants: [],
      return_inflows: "25.0000", transfer_inflows: "0.0000",
    },
    categories: [{ name: "Groceries", amount: "250.0000", transaction_count: 1, share_percent: "100.00" }],
    top_merchants: [{ name: "Carrefour", amount: "250.0000", transaction_count: 1, share_percent: "50.00" }],
    comparison: { state: "available", previous_month: "2026-08", metrics: [
      { name: "outflow", current: "500.0000", previous: "100.0000", delta: "400.0000", percent: "400.00", scale_percent: "0.00" },
    ], categories: [] },
    insights: [{ code: "outflow_change", metric: "outflow", subject: null, current: "500.0000", previous: "100.0000", delta: "400.0000", total_delta: null, contribution_percent: null, text: "Outflow increased by AED 400.0000 compared with 2026-08." }],
    trend: [{ month: "2026-08", totals: { ...totals, spending: "100.0000" }, spending_scale_percent: "40.00", income_scale_percent: "100.00", outflow_scale_percent: "100.00" }, { month: "2026-09", totals, spending_scale_percent: "100.00", income_scale_percent: "100.00", outflow_scale_percent: "100.00" }],
  }],
};

it("renders API analytics, calculation evidence and private navigation", async () => {
  vi.spyOn(api, "intelligence").mockResolvedValue(data);
  render(<Shell><Overview /></Shell>);
  expect(await screen.findByText("1,525.00 AED")).toBeInTheDocument();
  expect(screen.getByText(data.currencies[0].insights[0].text)).toBeInTheDocument();
  await userEvent.click(screen.getByText("See the calculation"));
  expect(screen.getByText(/Selected month: 500.00 AED/)).toBeVisible();
  expect(screen.getByText("Groceries")).toBeInTheDocument();
  expect(screen.getByText("Carrefour")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "Transactions" })).toHaveAttribute("href", "/app/transactions");
  expect(screen.getByRole("link", { name: "Import statement" })).toHaveAttribute("href", "/app/import");
});

it("explains an empty history with a real import link", async () => {
  vi.spyOn(api, "intelligence").mockResolvedValue({ ...data, month: null, available_months: [], currencies: [] });
  render(<Overview />);
  expect(await screen.findByText("Import your first statement to begin.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Import statement" })).toHaveAttribute("href", "/app/import");
  expect(screen.queryByText("1,525.00 AED")).not.toBeInTheDocument();
});

it("shows one-month context without inventing comparison insights", async () => {
  vi.spyOn(api, "intelligence").mockResolvedValue({ ...data, currencies: [{ ...data.currencies[0], comparison: { state: "insufficient_history", previous_month: "2026-08", metrics: [], categories: [] }, insights: [] }] });
  render(<Overview />);
  expect(await screen.findByText(/You have enough data to understand this month/)).toBeInTheDocument();
  expect(screen.queryByText(/Outflow increased/)).not.toBeInTheDocument();
});

it("switches currencies without combining totals", async () => {
  vi.spyOn(api, "intelligence").mockResolvedValue({ ...data, currencies: [data.currencies[0], { ...data.currencies[0], currency: "USD", insights: [] }] });
  render(<Overview />);
  await screen.findByText("1,525.00 AED");
  await userEvent.click(screen.getByRole("button", { name: "USD" }));
  expect(screen.getByText("1,525.00 USD")).toBeInTheDocument();
  expect(screen.queryByText("1,525.00 AED")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "USD" })).toHaveAttribute("aria-pressed", "true");
});

it("clears stale panels on period change, loads the requested month and ignores unmounted responses", async () => {
  let resolve: (value: OverviewData) => void = () => {};
  const fetcher = vi.spyOn(api, "intelligence").mockResolvedValueOnce(data).mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
  const view = render(<Overview />);
  await screen.findByText("1,525.00 AED");
  await userEvent.selectOptions(screen.getByLabelText("Month"), "2026-08");
  expect(fetcher).toHaveBeenLastCalledWith("2026-08");
  expect(screen.queryByText("1,525.00 AED")).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveAccessibleName("Loading your financial overview");
  view.unmount();
  resolve(data);
  await waitFor(() => expect(screen.queryByText("1,525.00 AED")).not.toBeInTheDocument());
});

it("shows a safe API error and retries", async () => {
  vi.spyOn(api, "intelligence").mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR")).mockResolvedValue(data);
  render(<Overview />);
  expect(await screen.findByRole("alert")).toHaveTextContent("retry");
  await userEvent.click(screen.getByRole("button", { name: "Retry Overview" }));
  expect(await screen.findByText("1,525.00 AED")).toBeInTheDocument();
});

it("validates exact API strings and uses the authenticated no-store transport", async () => {
  expect(overviewSchema.safeParse(data).success).toBe(true);
  expect(overviewSchema.safeParse({ ...data, currencies: [{ ...data.currencies[0], totals: { ...totals, income: 2000 } }] }).success).toBe(false);
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(data)));
  await api.intelligence("2026-08");
  expect(fetcher).toHaveBeenCalledWith("/api/v1/analytics/intelligence?month=2026-08", expect.objectContaining({ credentials: "same-origin", cache: "no-store" }));
});

it("switches date patterns and progressively discloses purchase detail", async () => {
  vi.spyOn(api, "intelligence").mockResolvedValue(data);
  render(<Overview />);
  await screen.findByRole("heading", { name: "The rhythm of your spending" });
  expect(screen.getByText("Saturday-Sunday")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Within the month" }));
  expect(screen.getByText("Days 21-31")).toBeVisible();
  expect(screen.queryByText("Saturday-Sunday")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Largest purchases" }));
  expect(screen.getByText("No purchases in this month.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Newly observed" }));
  expect(screen.getByText(/does not establish a first-ever purchase/)).toBeVisible();
});

it("renders ranked changes with expandable arithmetic disclosure", async () => {
  vi.spyOn(api, "intelligence").mockResolvedValue({ ...data, currencies: [{ ...data.currencies[0], comparison: {
    ...data.currencies[0].comparison,
    categories: [{ name: "Housing", current: "500.0000", previous: "100.0000", delta: "400.0000", percent: "400.00", scale_percent: "100.00" }],
  } }] });
  render(<Overview />);
  const why = await screen.findByText("Why Housing changed");
  await userEvent.click(why);
  expect(screen.getByText(/This is a change in imported category totals/)).toBeVisible();
  expect(screen.getByRole("heading", { name: "Spending drivers" })).toBeVisible();
});

it("explains insufficient baseline and recurring history without fabricated estimates", async () => {
  vi.spyOn(api, "intelligence").mockResolvedValue(data);
  render(<Overview />);
  expect(await screen.findByText("Your baseline needs more history")).toBeVisible();
  expect(screen.getByText("More history unlocks recurring patterns")).toBeVisible();
  expect(screen.queryByText("Estimated monthly pattern")).not.toBeInTheDocument();
});

it("renders baseline bands and recurring evidence with actual versus estimated spending", async () => {
  const currency = structuredClone(data.currencies[0]);
  currency.baselines.metrics[0] = { ...currency.baselines.metrics[0], state: "available",
    mean: "100.0000", low: "90.0000", high: "110.0000", average_three: "100.0000", average_six: null,
    delta: "150.0000", relative_percent: "150.00", position: "above", current_scale: "90.91",
    low_scale: "32.73", high_scale: "40.00", mean_scale: "36.36", months: ["2026-06", "2026-07", "2026-08"], values: ["90.0000", "100.0000", "110.0000"],
  };
  currency.recurring = { ...currency.recurring, state: "likely_recurring", monthly_estimate: "49.0000", annual_estimate: "588.0000", matched_spending: "50.0000", other_spending: "200.0000", matched_share_percent: "20.00", payments: [{
    merchant: "Netflix", typical_amount: "49.0000", annual_estimate: "588.0000", frequency: "monthly", newly_qualified: true, reason: "Three monthly charges within 5%.", share_percent: "100.00",
    evidence: ["06", "07", "08"].map((month) => ({identifier: `00000000-0000-4000-8000-0000000000${month}`, day: `2026-${month}-05`, amount: "49.0000"})),
  }] };
  vi.spyOn(api, "intelligence").mockResolvedValue({ ...data, currencies: [currency] });
  render(<Overview />);
  expect(await screen.findByText("Above the observed range")).toBeVisible();
  await userEvent.click(screen.getByText("Why this looks recurring"));
  expect(screen.getByText("Three monthly charges within 5%.")).toBeVisible();
  expect(screen.getByRole("link", {name: "2026-07-05"})).toHaveAttribute("href", "/app/transactions/00000000-0000-4000-8000-000000000007");
  expect(screen.getByText("Newly qualified this month")).toBeVisible();
  expect(screen.getByText("Matched charges")).toBeVisible();
  await userEvent.selectOptions(screen.getByLabelText("Compare with your history"), "metric:Income");
  expect(screen.queryByText("Above the observed range")).not.toBeInTheDocument();
  expect(screen.getByText("Your baseline needs more history")).toBeVisible();
});
