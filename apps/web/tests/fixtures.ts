import type { ImportPreview, Transaction } from "@/lib/api";
export const id = "d86d3606-6daf-41ec-91b9-d332c5e79420";
export const transaction: Transaction = {
  id,
  transaction_date: "2026-08-01",
  amount: "-48.5000",
  currency: "AED",
  raw_description: "TALABAT AE 12345",
  normalized_description: "TALABAT AE 12345",
  merchant: "Talabat",
  category: "Food & Dining",
  categorization_source: "merchant_rule",
  categorization_reason: "Merchant matched Talabat rule.",
  automatic_category: "Food & Dining",
  automatic_source: "merchant_rule",
  automatic_reason: "Merchant matched Talabat rule.",
  rule_id: "talabat",
  rule_version: "understanding-v1",
  normalization_version: "description-v1",
  version: 1,
  enrichment_persisted: true,
};
export const preview: ImportPreview = {
  id,
  status: "ready",
  total_rows: 1,
  valid_rows: 1,
  invalid_rows: 0,
  accepted_rows: 0,
  period_start: "2026-08-01",
  period_end: "2026-08-01",
  currencies: ["AED"],
  expires_at: "2026-09-09T12:00:00Z",
  can_finalize: true,
  rows: {
    items: [
      {
        source_row_number: 2,
        transaction_date: "2026-08-01",
        description: "TALABAT AE 12345",
        amount: "-48.5000",
        currency: "AED",
        errors: [],
      },
    ],
    next_after_row: null,
  },
};
