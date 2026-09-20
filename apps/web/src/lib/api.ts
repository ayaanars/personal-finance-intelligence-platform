import { planSchema, type GoalInput } from "./goals";
import { z } from "zod";
import { intelligenceSchema, overviewSchema } from "./analytics";
import { unusualSchema } from "./unusual";
import { relationshipsSchema } from "./relationships";

export const categories = [
  "Income",
  "Groceries",
  "Food & Dining",
  "Transport",
  "Shopping",
  "Entertainment",
  "Housing",
  "Bills & Utilities",
  "Health",
  "Education",
  "Travel",
  "Transfers",
  "Cash / ATM",
  "Banking Fees",
  "Other",
] as const;
const category = z.enum(categories);
const money = z.string().regex(/^-?\d+\.\d{4}$/);
const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
export const userSchema = z.object({
  id: z.uuid(),
  email: z.string(),
  workspace: z.object({ id: z.uuid(), display_name: z.string() }),
});
export const transactionSchema = z.object({
  id: z.uuid(),
  transaction_date: date,
  amount: money,
  currency: z.enum(["AED", "USD", "EUR", "GBP"]),
  raw_description: z.string(),
  normalized_description: z.string(),
  merchant: z.string().nullable(),
  merchant_code: z.string().nullable().optional(),
  merchant_source: z.string().nullable().optional(),
  category,
  categorization_source: z.string(),
  categorization_reason: z.string(),
  automatic_category: category,
  automatic_source: z.string(),
  automatic_reason: z.string(),
  rule_id: z.string(),
  rule_version: z.string(),
  normalization_version: z.string(),
  version: z.number().int().nonnegative(),
  enrichment_persisted: z.boolean(),
});
export const transactionPageSchema = z.object({
  items: z.array(transactionSchema).max(100),
  page: z.object({ next_cursor: z.string().nullable(), has_more: z.boolean() }),
});
const rowSchema = z.object({
  source_row_number: z.number().int(),
  transaction_date: date.nullable(),
  description: z.string().nullable(),
  amount: money.nullable(),
  currency: z.string().nullable(),
  errors: z.array(z.object({ code: z.string(), message: z.string() })),
});
export const rowPageSchema = z.object({
  items: z.array(rowSchema).max(100),
  next_after_row: z.number().int().nullable(),
});
export const importSchema = z.object({
  id: z.uuid(),
  status: z.enum(["ready", "invalid", "completed", "expired"]),
  total_rows: z.number().int(),
  valid_rows: z.number().int(),
  invalid_rows: z.number().int(),
  accepted_rows: z.number().int(),
  period_start: date.nullable(),
  period_end: date.nullable(),
  currencies: z.array(z.string()),
  expires_at: z.string(),
  can_finalize: z.boolean(),
  rows: rowPageSchema,
});
const finalizeSchema = z.object({
  id: z.uuid(),
  status: z.literal("completed"),
  accepted_rows: z.number().int(),
  finalized_at: z.string(),
});
export type User = z.infer<typeof userSchema>;
export type Transaction = z.infer<typeof transactionSchema>;
export type ImportPreview = z.infer<typeof importSchema>;
export type RowPage = z.infer<typeof rowPageSchema>;
export type Category = (typeof categories)[number];

const messages: Record<string, string> = {
  INVALID_CREDENTIALS: "Email or password did not match. Please try again.",
  REGISTRATION_FAILED:
    "We couldn't create this account. Check your details or try signing in.",
  AUTH_REQUIRED: "Your session has ended. Sign in again to continue.",
  CSRF_INVALID:
    "Your session security token changed, possibly in another tab. Please retry.",
  VERSION_CONFLICT:
    "This category changed elsewhere. Review the latest details before saving again.",
  IMPORT_EXPIRED:
    "This preview has expired. Upload the CSV again to review it.",
  IMPORT_INVALID:
    "This import contains invalid rows. Fix the CSV and upload it again.",
  FINALIZE_KEY_MISMATCH:
    "This import was already finalized. Refresh the preview to see its status.",
  VALIDATION_ERROR:
    "Check your input and try again. Passwords must contain 15 to 128 characters.",
};
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(
      messages[code] ??
        (status === 413
          ? "The CSV exceeds the 5 MiB or 25,000-row limit."
          : status === 422
            ? "The CSV or request could not be read. Check the canonical format and try again."
            : status === 404
              ? "This record is unavailable. Return to your history or upload a new statement."
              : status === 409
                ? "This request conflicts with an earlier action. Refresh before continuing."
                : "We couldn't reach LedgerX reliably. Check your connection and retry."),
    );
  }
}
export const errorMessage = (error: unknown) =>
  error instanceof ApiError
    ? error.message
    : "We couldn't complete this request. Check your connection and retry.";

// One transport boundary. Never persist tokens, credentials, responses or CSV bytes.
async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...init,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR");
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const parsed = z
      .object({ error: z.object({ code: z.string() }) })
      .safeParse(body);
    const error = new ApiError(
      response.status,
      parsed.success ? parsed.data.error.code : "HTTP_ERROR",
    );
    if (
      response.status === 401 &&
      path !== "/me" &&
      !path.startsWith("/auth/login")
    )
      window.dispatchEvent(new Event("ledgerx:unauthorized"));
    throw error;
  }
  const parsed = schema.safeParse(
    response.status === 204
      ? undefined
      : await response.json().catch(() => null),
  );
  if (!parsed.success) throw new ApiError(0, "INVALID_RESPONSE");
  return parsed.data;
}
async function mutate<T>(
  path: string,
  schema: z.ZodType<T>,
  init: RequestInit,
) {
  const { csrf_token } = await request(
    "/auth/csrf",
    z.object({ csrf_token: z.string() }),
  );
  return request(path, schema, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
      "X-CSRF-Token": csrf_token,
    },
  });
}
export const api = {
  plan: (month?: string) => request(`/goals${month ? `?month=${encodeURIComponent(month)}` : ""}`, planSchema),
  removeGoal: (body: Omit<GoalInput, "target" | "active">) => mutate("/goals", z.undefined(), {method:"DELETE", body:JSON.stringify(body)}),
  saveGoal: (body: GoalInput) => mutate("/goals", z.undefined(), {method:"PUT", body:JSON.stringify(body)}),
  relationships: (month?: string) => request(
    `/analytics/relationships${month ? `?month=${encodeURIComponent(month)}` : ""}`, relationshipsSchema,
  ),
  unusual: (month?: string) => request(
    `/analytics/unusual${month ? `?month=${encodeURIComponent(month)}` : ""}`, unusualSchema,
  ),
  intelligence: (month?: string) => request(
    `/analytics/intelligence${month ? `?month=${encodeURIComponent(month)}` : ""}`,
    intelligenceSchema,
  ),
  overview: (month?: string) => request(
    `/analytics/overview${month ? `?month=${encodeURIComponent(month)}` : ""}`,
    overviewSchema,
  ),
  me: () => request("/me", userSchema),
  credentials: (mode: "login" | "register", email: string, password: string) =>
    request(`/auth/${mode}`, mode === "login" ? z.unknown() : userSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
  logout: () =>
    mutate("/auth/logout", z.undefined(), { method: "POST", body: "{}" }),
  transactions: (cursor?: string) =>
    request(
      `/transactions?limit=25${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
      transactionPageSchema,
    ),
  transaction: (id: string) =>
    request(`/transactions/${encodeURIComponent(id)}`, transactionSchema),
  reprocess: (transaction: Transaction) =>
    mutate(`/transactions/${transaction.id}/reprocess`, transactionSchema, { method: "POST", body: "{}" }),
  category: (transaction: Transaction, category: Category | null, preference: "keep" | "save" | "forget" = "keep") =>
    mutate(`/transactions/${transaction.id}/category`, transactionSchema, {
      method: "PATCH",
      headers: { "If-Match": `"${transaction.version}"` },
      body: JSON.stringify({ category, ...(preference !== "keep" ? { merchant_preference: preference } : {}) }),
    }),
  upload: (file: File, key: string) =>
    mutate("/imports", importSchema, {
      method: "POST",
      headers: {
        "Content-Type": "text/csv",
        "X-Filename": "statement.csv",
        "Idempotency-Key": key,
      },
      body: file,
    }),
  preview: (id: string) =>
    request(`/imports/${encodeURIComponent(id)}`, importSchema),
  rows: (id: string, after: number) =>
    request(
      `/imports/${encodeURIComponent(id)}/rows?limit=50&after_row=${after}`,
      rowPageSchema,
    ),
  finalize: (id: string, key: string) =>
    mutate(`/imports/${encodeURIComponent(id)}/finalize`, finalizeSchema, {
      method: "POST",
      headers: { "Idempotency-Key": key },
      body: "{}",
    }),
};

// String-only presentation preserves every digit; no float conversion or rounding.
export function displayMoney(amount: string, currency: string) {
  const negative = amount.startsWith("-");
  const [whole, fraction] = amount.replace(/^[+-]/, "").split(".");
  const digits = (fraction ?? "").replace(/0+$/, "").padEnd(2, "0");
  return `${negative ? "−" : "+"}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${digits} ${currency}`;
}
