import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { IntelligencePage, Overview } from "@/features/overview";
import { RecurringCommitments, YourNormal } from "@/features/overview-history";
import { Shell } from "@/components/shell";
import { api, ApiError } from "@/lib/api";
import { intelligenceSchema as overviewSchema, type IntelligenceData as OverviewData } from "@/lib/analytics";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }), usePathname: () => "/app" }));
import { data } from "./intelligence-fixture";

it("renders API analytics, calculation evidence and private navigation", async () => {
  vi.spyOn(api, "intelligence").mockResolvedValue(data);
  render(<Shell><Overview /></Shell>);
  expect(await screen.findByText("1,525.00 AED")).toBeInTheDocument();
  expect(screen.getByText(data.currencies[0].insights[0].text)).toBeInTheDocument();
  await userEvent.click(screen.getByText("See the calculation"));
  expect(screen.getByText(/Selected month: 500.00 AED/)).toBeVisible();
  expect(screen.getByRole("link", {name: "Trends"})).toHaveAttribute("href", "/app/trends");
  expect(screen.getByRole("link", {name: "Behaviour"})).toHaveAttribute("href", "/app/behaviour");
  expect(screen.queryByText("The rhythm of your spending")).not.toBeInTheDocument();
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
  expect(overviewSchema.safeParse({ ...data, currencies: [{ ...data.currencies[0], totals: { ...data.currencies[0].totals, income: 2000 } }] }).success).toBe(false);
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(data)));
  await api.intelligence("2026-08");
  expect(fetcher).toHaveBeenCalledWith("/api/v1/analytics/intelligence?month=2026-08", expect.objectContaining({ credentials: "same-origin", cache: "no-store" }));
});

it("switches date patterns and progressively discloses purchase detail", async () => {
  vi.spyOn(api, "intelligence").mockResolvedValue(data);
  render(<IntelligencePage page="behaviour" />);
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
  render(<><YourNormal data={currency}/><RecurringCommitments data={currency}/></>);
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
