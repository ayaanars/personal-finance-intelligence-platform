import type { IntelligenceData as OverviewData } from "@/lib/analytics";
const totals = {
    income: "2000.0000", inflows: "2025.0000", other_inflows: "25.0000", outflow: "500.0000",
    net_cash_flow: "1525.0000", spending: "250.0000", cash_out: "50.0000", transfers_out: "200.0000", transaction_count: 5,
};
export const data: OverviewData = {
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
            recurring: { state: "insufficient_history", payments: [], candidates: [], monthly_estimate: "0.0000", annual_estimate: "0.0000", matched_spending: "0.0000", other_spending: "250.0000", matched_share_percent: "0.00", method: "Likely patterns, not confirmed subscriptions." },
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
