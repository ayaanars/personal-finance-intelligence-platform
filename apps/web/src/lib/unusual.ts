import { z } from "zod";
const decimal = z.string().regex(/^-?\d+\.\d{4}$/);
export const unusualSchema = z.object({
    month: z.string().nullable(), available_months: z.array(z.string()).max(120),
    methodology_version: z.enum(["unusual-v1", "unusual-v2"]), coverage_note: z.string(),
    currencies: z.array(z.object({
        currency: z.enum(["AED", "USD", "EUR", "GBP"]),
        state: z.enum(["available", "insufficient_history", "no_activity"]),
        prior_months: z.array(z.string()).max(6), historical_purchases: z.number().int().nonnegative(),
        ml_state: z.enum(["active", "insufficient_history", "unavailable", "no_activity"]),
        total: z.number().int().nonnegative(),
        items: z.array(z.object({
            basis: z.enum(["historical", "current_month"]).optional(),
            identifier: z.string(), subject: z.string(), day: z.string().nullable(),
            severity: z.enum(["Notable", "High"]), transaction_ids: z.array(z.uuid()).max(5),
            ml_supported: z.boolean(), evidence: z.array(z.object({
                code: z.string(), explanation: z.string(), current: decimal,
                reference: decimal.nullable(), unit: z.enum(["money", "count"]),
                ratio: z.string().regex(/^\d+\.\d{2}$/).nullable(),
                reference_scale: z.string().regex(/^\d+\.\d{2}$/).nullable(),
            })),
        })).max(100),
    })).max(4),
});
export type UnusualData = z.infer<typeof unusualSchema>;
