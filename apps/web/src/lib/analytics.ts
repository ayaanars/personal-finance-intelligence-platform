import { z } from "zod";

const money = z.string().regex(/^-?\d+\.\d{4}$/);
const percent = z.string().regex(/^-?\d+\.\d{2}$/);
const month = z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/);
const totals = z.object({
  inflows: money, income: money, other_inflows: money, outflow: money,
  net_cash_flow: money, spending: money, transfers_out: money, cash_out: money,
  transaction_count: z.number().int().nonnegative(),
});
const breakdown = z.object({
  name: z.string().nullable(), amount: money,
  transaction_count: z.number().int().nonnegative(), share_percent: percent.nullable(),
});
const change = z.object({
  name: z.string(), current: money, previous: money, delta: money, percent: percent.nullable(),
  scale_percent: percent.default("0.00"),
});
export const overviewSchema = z.object({
  month: month.nullable(), available_months: z.array(month).max(120),
  window_start: month.nullable(), methodology_version: z.literal("intelligence-v1"),
  coverage_note: z.string(),
  currencies: z.array(z.object({
    currency: z.enum(["AED", "USD", "EUR", "GBP"]), totals,
    categories: z.array(breakdown).max(15), top_merchants: z.array(breakdown).max(5),
    comparison: z.object({
      state: z.enum(["available", "insufficient_history", "no_activity"]),
      previous_month: month, metrics: z.array(change), categories: z.array(change),
    }),
    insights: z.array(z.object({
      code: z.string(), text: z.string(), metric: z.string(), subject: z.string().nullable(),
      current: money, previous: money, delta: money,
      total_delta: money.nullable(), contribution_percent: percent.nullable(),
    })).max(4),
    trend: z.array(z.object({ month, totals, spending_scale_percent: percent, income_scale_percent: percent.default("0.00"), outflow_scale_percent: percent.default("0.00") })).max(6),
    observed_start: z.string().nullable(), observed_end: z.string().nullable(),
  })).max(4),
});
export type OverviewData = z.infer<typeof overviewSchema>;
export type CurrencyOverview = OverviewData["currencies"][number];

const baseCurrency = overviewSchema.shape.currencies.element;
const behaviourSchema = z.object({
  spending_count: z.number().int().nonnegative(), average_purchase: money.nullable(),
  active_spending_days: z.number().int().min(0).max(31),
  weekday_weekend: z.array(breakdown).length(2), month_parts: z.array(breakdown).length(3),
  top_spending_merchants: z.array(breakdown).max(5),
  top_five_category_share: percent.nullable(), top_five_merchant_share: percent.nullable(),
  largest_purchases: z.array(z.object({ identifier: z.uuid(), day: z.string(), merchant: z.string().nullable(), category: z.string(), amount: money })).max(5),
  merchant_changes: z.array(change).max(10), newly_observed_merchants: z.array(breakdown).max(5),
  return_inflows: money, transfer_inflows: money,
});
const baseline = z.object({
  name: z.string(), kind: z.enum(["metric", "category"]),
  state: z.enum(["available", "insufficient_history", "no_activity"]),
  current: money.nullable(), mean: money.nullable(), low: money.nullable(), high: money.nullable(),
  average_three: money.nullable(), average_six: money.nullable(), delta: money.nullable(),
  relative_percent: percent.nullable(), position: z.enum(["above", "within", "below"]).nullable(),
  current_scale: percent.nullable(), low_scale: percent.nullable(), high_scale: percent.nullable(), mean_scale: percent.nullable(),
  months: z.array(month).max(6), values: z.array(money).max(6),
});
const recurringPayment = z.object({
  merchant: z.string(), typical_amount: money, annual_estimate: money, frequency: z.literal("monthly"),
  newly_qualified: z.boolean().nullable(), reason: z.string(), share_percent: percent.nullable(),
  evidence: z.array(z.object({identifier: z.uuid(), day: z.string(), amount: money})).length(3),
});
export const intelligenceSchema = overviewSchema.extend({
  intelligence_version: z.literal("longitudinal-v1"),
  currencies: z.array(baseCurrency.extend({
    trend: z.array(baseCurrency.shape.trend.element).max(7),
    behaviour: behaviourSchema,
    baselines: z.object({ prior_months: z.array(month).max(6), observed_months: z.number().int().min(0).max(7), metrics: z.array(baseline).length(3), categories: z.array(baseline).max(15), method: z.string() }),
    recurring: z.object({
      state: z.enum(["likely_recurring", "insufficient_history", "insufficient_evidence", "no_activity"]),
      payments: z.array(recurringPayment),
      candidates: z.array(z.object({observed_months: z.number().int().nonnegative().optional(), current_amount: money.optional(), evidence: z.array(z.object({identifier:z.uuid(), day:z.string(), amount:money})).max(5).optional(), merchant: z.string(), reason: z.enum(["fewer_than_three_months", "multiple_charges", "timing_not_regular", "amounts_vary"])})).max(5),
      monthly_estimate: money, annual_estimate: money, matched_spending: money, other_spending: money,
      matched_share_percent: percent.nullable(), method: z.string(),
    }),
  })).max(4),
});
export type IntelligenceData = z.infer<typeof intelligenceSchema>;
export type IntelligenceCurrency = IntelligenceData["currencies"][number];
export type BaselineData = z.infer<typeof baseline>;
