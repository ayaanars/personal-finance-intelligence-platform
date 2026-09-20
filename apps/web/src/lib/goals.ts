import { z } from "zod";
const money = z.string().regex(/^-?\d+\.\d{4}$/);
export const planSchema = z.object({
    month: z.string(), available_months: z.array(z.string()),
    goals: z.array(z.object({ kind: z.string(), currency: z.string(), target: money, active: z.boolean(), actual: money, projected: money.nullable(), status: z.string(), pace_target: money })),
    currencies: z.array(z.object({ currency: z.string(), state: z.enum(["estimate", "historical", "unavailable"]), quality: z.string(), elapsed_days: z.number(), days_in_month: z.number(), history_months: z.number(), observed_span_days: z.number(), last_activity: z.string().nullable(), actual_spending: money, actual_outflow: money, actual_net_cash_flow: money, projected_spending: money.nullable(), projected_outflow: money.nullable(), projected_net_cash_flow: money.nullable(), remaining_recurring: money, commitments: z.array(z.object({ merchant: z.string(), amount: money, state: z.enum(["observed", "remaining", "overdue"]), expected_day: z.string() })), explanation: z.string(), insight: z.string().nullable() }))
});
export type Plan = z.infer<typeof planSchema>;
export type GoalInput = {
    month: string;
    currency: string;
    kind: string;
    target: string;
    active: boolean;
};
