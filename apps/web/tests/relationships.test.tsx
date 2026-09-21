import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { relationshipsSchema } from "@/lib/relationships";
import { Relationships } from "@/features/relationships";
import { IntelligencePage } from "@/features/overview";
import { Shell } from "@/components/shell";
import { data as overview } from "./intelligence-fixture";
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }), usePathname: () => "/app/relationships" }));
const months = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"];
const item = {
    code: "spending_net", x_label: "Monthly spending", y_label: "Net cash flow", direction: "opposite",
    interpretation: "Higher monthly spending tended to coincide with lower net cash flow.", caveat: "Spending contributes to outflow; shared arithmetic matters.",
    months, sample_count: 6, coefficient: "-1.000", median_x: "350.0000",
    higher: { months: months.slice(3), x_mean: "500.0000", y_mean: "500.0000" },
    other: { months: months.slice(0, 3), x_mean: "200.0000", y_mean: "800.0000" },
    points: months.map((month, index) => ({ month, previous_month: null, x: `${(index + 1) * 100}.0000`, y: `${900 - index * 100}.0000` })), evolution: null,
};
const report = relationshipsSchema.parse({
    month: "2026-09", window_start: "2025-09", available_months: months, methodology_version: "relationships-v1", minimum_observations: 6,
    coverage_note: "Associations only; partial months can influence totals.", currencies: [{
            currency: "AED", state: "available", observed_months: months, missing_months: [], items: [item],
            screening: ["spending_net", "weekend_outflow", "cash_spending", "recurring_net", "dining_change_net"].map(code => ({ code, sample_count: 6, state: code === "spending_net" ? "supported" : "not_clear" })),
        }],
});
it("renders associations, group evidence and exploratory paired trends", async () => {
    vi.spyOn(api, "relationships").mockResolvedValue(report);
    render(<Relationships />);
    await screen.findByText(item.interpretation);
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", expect.stringContaining("Each dot is one observed month"));
    expect(screen.getByText("500.00 AED", { selector: "strong" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Paired trends" }));
    expect(screen.getAllByRole("img")).toHaveLength(2);
    await userEvent.click(screen.getByText("History, methodology & how the relationship changed"));
    expect(screen.getByRole("table")).toBeVisible();
    expect(screen.getByText(/Twelve usable observations/)).toBeVisible();
    expect(screen.queryByText(/caused/)).not.toBeInTheDocument();
});
it("shows one relationship on Insights and no new Overview section", async () => {
    vi.spyOn(api, "relationships").mockResolvedValue(report);
    vi.spyOn(api, "intelligence").mockResolvedValue(overview);
    const view = render(<IntelligencePage page="insights"/>);
    await screen.findByRole("heading", { name: item.interpretation });
    expect(screen.getByRole("link", { name: "Explore longer-term relationships ↗" })).toHaveAttribute("href", "/app/relationships");
    view.unmount();
    render(<IntelligencePage page="overview"/>);
    await screen.findByRole("heading", { name: "What changed?" });
    expect(screen.queryByText(item.interpretation)).not.toBeInTheDocument();
});
it("makes insufficient history and errors explicit", async () => {
    const fetcher = vi.spyOn(api, "relationships").mockResolvedValue({ ...report, currencies: [{ ...report.currencies[0], state: "insufficient_history", items: [], observed_months: months.slice(0, 2) }] });
    const view = render(<Relationships />);
    await screen.findByRole("heading", { name: "More history is needed" });
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    view.unmount();
    fetcher.mockRejectedValue(new Error("Unavailable"));
    render(<Relationships />);
    await screen.findByRole("alert");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
});
it("groups all routes in the requested navigation order", () => {
    render(<Shell><p>Content</p></Shell>);
    const primary = screen.getByRole("navigation", { name: "Primary" });
    const intelligence = within(primary).getByRole("group", { name: "Intelligence" });
    expect(within(intelligence).getAllByRole("link").map(link => link.getAttribute("href"))).toEqual([
        "/app", "/app/insights", "/app/trends", "/app/unusual", "/app/relationships", "/app/goals", "/app/recurring", "/app/behaviour",
    ]);
    expect(within(within(primary).getByRole("group", { name: "Data" })).getAllByRole("link").map(link => link.getAttribute("href"))).toEqual(["/app/transactions", "/app/import"]);
    expect(screen.getByRole("link", { name: "Relationships" })).toHaveAttribute("aria-current", "page");
});

it("keeps current composition visible while one-month relationships develop", async () => {
  vi.spyOn(api,"relationships").mockResolvedValue({...report, currencies:report.currencies.map(c=>({...c,state:"insufficient_history" as const,items:[],observed_months:["2026-09"]}))});
  vi.spyOn(api,"intelligence").mockResolvedValue(overview);
  render(<Relationships />);
  expect(await screen.findByText("Here’s what we know now")).toBeVisible();
  expect(screen.getByText("Category composition")).toBeVisible();
  expect(screen.getByText("More history is needed")).toBeVisible();
  expect(screen.queryByText(item.interpretation)).not.toBeInTheDocument();
});
