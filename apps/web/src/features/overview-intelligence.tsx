"use client";
import { dateLabel } from "@/lib/dates";

import Link from "next/link";
import { useState } from "react";
import type { IntelligenceCurrency } from "@/lib/analytics";
import { displayMoney } from "@/lib/api";

const amount = (value: string, currency: string) => displayMoney(value, currency).replace(/^\+/, "");

export function BehaviourStory({ data }: { data: IntelligenceCurrency }) {
  const [pattern, setPattern] = useState<"week" | "month">("week");
  const [view, setView] = useState<"merchants" | "categories" | "purchases" | "new">(data.comparison.state === "available" ? "merchants" : "purchases");
  const b = data.behaviour;
  const changes = view === "categories" ? data.comparison.categories : b.merchant_changes;
  const patterns = pattern === "week" ? b.weekday_weekend : b.month_parts;
  return <>
    <section className="behaviour-section" aria-labelledby="behaviour-title">
      <h2 id="behaviour-title">The rhythm of your spending</h2>
      <p>When you spend, how often, and where purchases concentrate.</p>
      <div className="behaviour-grid">
        <div>
          <div className="segmented" role="group" aria-label="Spending pattern">
            <button aria-pressed={pattern === "week"} onClick={() => setPattern("week")}>Weekday / weekend</button>
            <button aria-pressed={pattern === "month"} onClick={() => setPattern("month")}>Within the month</button>
          </div>
          <ol className="pattern-bars">{patterns.map((row) => <li key={row.name}>
            <div><strong>{row.name}</strong><span>{amount(row.amount, data.currency)}</span></div>
            <div className="pattern-bar" aria-hidden="true" style={{ width: `${row.share_percent ?? "0"}%` }} />
            <p>{row.transaction_count} {row.transaction_count === 1 ? "purchase" : "purchases"} · {row.share_percent === null ? "No spending share" : `${row.share_percent}% share`}</p>
          </li>)}</ol>
          <p className="overview-note">{pattern === "week" ? "Saturday/Sunday defines weekend here. " : "Month segments have unequal durations. "}Totals reflect observed activity, not daily rates or a complete month.</p>
        </div>
        <dl className="behaviour-stats">
          <div><dt>Average purchase</dt><dd>{b.average_purchase ? amount(b.average_purchase, data.currency) : "No purchases"}</dd><p>Gross spending ÷ purchase count</p></div>
          <div><dt>Purchase frequency</dt><dd>{b.spending_count} <small>purchases</small></dd><p>Across {b.active_spending_days} observed spending days</p></div>
          <div><dt>Top five categories</dt><dd>{b.top_five_category_share === null ? "No spending" : `${b.top_five_category_share}%`}</dd><p>Share of gross spending</p></div>
          <div><dt>Top five merchants</dt><dd>{b.top_five_merchant_share === null ? "No spending" : `${b.top_five_merchant_share}%`}</dd><p>Share of gross spending; unknown grouped together</p></div>
        </dl>
      </div>
    </section>
    <section className="purchase-explorer" aria-labelledby="explore-title">
      <h2 id="explore-title">A closer look at purchases</h2>
      <div className="segmented" role="group" aria-label="Purchase detail">
        <button aria-pressed={view === "merchants"} onClick={() => setView("merchants")}>Merchant momentum</button>
        <button aria-pressed={view === "categories"} onClick={() => setView("categories")}>Category momentum</button>
        <button aria-pressed={view === "purchases"} onClick={() => setView("purchases")}>Largest purchases</button>
        <button aria-pressed={view === "new"} onClick={() => setView("new")}>Newly observed</button>
      </div>
      {view === "merchants" || view === "categories" ? <>
        <p className="section-intro">Spending changes vs the immediately previous month. Merchant and category views overlap.</p>
        {changes.length ? <ol className="momentum-list">{changes.map((row) => <li key={row.name}>
          <div><strong>{row.name}</strong><span>{displayMoney(row.delta, data.currency)}</span></div>
          <div className={`driver-bar ${row.delta.startsWith("-") ? "decrease" : "increase"}`} aria-hidden="true" style={{ width: `${row.scale_percent}%` }} />
          <span>{amount(row.previous, data.currency)} → {amount(row.current, data.currency)}</span>
        </li>)}</ol> : <p className="notice">History-based momentum needs activity in two adjacent months. Current purchase details remain available.</p>}
      </> : view === "purchases" ? <ol className="purchase-list">{b.largest_purchases.length ? b.largest_purchases.map((row) => <li key={row.identifier}>
        <div><Link href={`/app/transactions/${row.identifier}`}>{row.merchant ?? "Unknown merchant"}</Link><p>{dateLabel(row.day)} · {row.category}</p></div><strong>{amount(row.amount, data.currency)}</strong>
      </li>) : <li>No purchases in this month.</li>}</ol> : <>
        <p className="section-intro">Known merchants appearing this month but absent from earlier imported activity in this window. This does not establish a first-ever purchase.</p>
        <ol className="purchase-list">{b.newly_observed_merchants.length ? b.newly_observed_merchants.map((row) => <li key={row.name}><strong>{row.name}</strong><span>{amount(row.amount, data.currency)}</span></li>) : <li>No newly observed merchants supported by this history.</li>}</ol>
      </>}
    </section>
    <section className="movement-section" aria-labelledby="movement-title">
      <h2 id="movement-title">Beyond purchases</h2><p>Money movement and adjustments keep their own meaning.</p>
      <dl className="movement-grid">
        <div><dt>Cash withdrawn</dt><dd>{amount(data.totals.cash_out, data.currency)}</dd><p>Destination of cash spending is unknown.</p></div>
        <div><dt>Transfers out / in</dt><dd>{amount(data.totals.transfers_out, data.currency)}<small>{amount(b.transfer_inflows, data.currency)} in</small></dd><p>Category interpretation, not reconciled transfers.</p></div>
        <div><dt>Refund / reimbursement signals</dt><dd>{amount(b.return_inflows, data.currency)}</dd><p>Positive return-rule matches, including cashback and reversals. Not netted against spending.</p></div>
      </dl>
    </section>
  </>;
}
