"use client";
import { useState } from "react";
import { ActivitySummary, type Activity } from "./transaction-activity";

// Public illustrative data only. Authenticated routes always read the real API.
const examples: Activity[] = [
  {
    merchant: "Talabat",
    normalized_description: "TALABAT AE 12345",
    raw_description: "TALABAT AE 12345",
    amount: "-48.5000",
    currency: "AED",
    category: "Food & Dining",
    transaction_date: "2026-08-01",
  },
  {
    merchant: "Carrefour",
    normalized_description: "CARREFOUR MOE",
    raw_description: "CARREFOUR MOE",
    amount: "-217.3000",
    currency: "AED",
    category: "Groceries",
    transaction_date: "2026-08-02",
  },
  {
    merchant: "Netflix",
    normalized_description: "NETFLIX.COM",
    raw_description: "NETFLIX.COM",
    amount: "-49.0000",
    currency: "AED",
    category: "Entertainment",
    transaction_date: "2026-08-07",
  },
];
export function ProductExample() {
  const [index, setIndex] = useState(0);
  const selected = examples[index];
  return (
    <figure className="product-example">
      <figcaption>
        Available today <span>Synthetic transactions</span>
      </figcaption>
      <div className="example-heading">
        <span className="brand">
          Ledger<span>X</span>
        </span>
        <span>Transaction history</span>
      </div>
      <div className="example-intro">
        <h2>The everyday, understood.</h2>
        <p>Three transactions. A clearer story.</p>
      </div>
      <div className="example-list" aria-label="Explore example transactions">
        {examples.map((activity, i) => (
          <button
            key={activity.merchant}
            onClick={() => setIndex(i)}
            aria-pressed={index === i}
            aria-label={`Explore ${activity.merchant} example`}
          >
            <ActivitySummary activity={activity} />
          </button>
        ))}
      </div>
      <div className="example-understanding" aria-live="polite">
        <span>From your statement</span>
        <code>{selected.raw_description}</code>
        <div className="understanding-result" key={index}>
          <span aria-hidden="true">↳</span>
          <div>
            <strong>{selected.merchant}</strong>
            <p>{selected.category}</p>
          </div>
          <span className="understanding-note">
            Merchant recognized
            <br />
            Category explained
          </span>
        </div>
      </div>
      <p className="example-footnote">
        You can review the reason and correct the category in your workspace.
      </p>
    </figure>
  );
}
