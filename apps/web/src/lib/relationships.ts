import { z } from "zod";
const money = z.string().regex(/^-?\d+\.\d{4}$/);
const month = z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/);
const months = z.array(month).max(13);
const direction = z.enum(["together", "opposite", "not_clear"]);
const group = z.object({ months, x_mean: money, y_mean: money });
const relationship = z.object({
    code: z.string(), x_label: z.string(), y_label: z.string(),
    direction: z.enum(["together", "opposite"]), interpretation: z.string(), caveat: z.string(),
    months, sample_count: z.number().int().min(6).max(13), coefficient: z.string().regex(/^-?[01]\.\d{3}$/),
    median_x: money, higher: group, other: group,
    points: z.array(z.object({ month, previous_month: month.nullable(), x: money, y: money })).min(6).max(13),
    evolution: z.object({ earlier_months: months, recent_months: months, earlier_direction: direction, recent_direction: direction }).nullable(),
});
export const relationshipsSchema = z.object({
    month: month.nullable(), window_start: month.nullable(), available_months: z.array(month).max(120),
    methodology_version: z.literal("relationships-v1"), minimum_observations: z.literal(6), coverage_note: z.string(),
    currencies: z.array(z.object({
        currency: z.enum(["AED", "USD", "EUR", "GBP"]),
        state: z.enum(["available", "insufficient_history", "no_clear_relationship", "no_activity"]),
        observed_months: months, missing_months: months, items: z.array(relationship).max(5),
        screening: z.array(z.object({ code: z.string(), sample_count: z.number().int().min(0).max(13), state: z.enum(["insufficient_history", "limited_variation", "not_clear", "supported"]) })).length(5),
    })).max(4),
});
export type RelationshipsData = z.infer<typeof relationshipsSchema>;
export type RelationshipData = z.infer<typeof relationship>;
