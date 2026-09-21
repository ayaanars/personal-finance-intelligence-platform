"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import type { IntelligenceCurrency, IntelligenceData } from "@/lib/analytics";
import { dateLabel, monthLabel } from "@/lib/dates";
import { amount } from "./intelligence-charts";

// Reuses the authoritative intelligence response; no separate first-month calculations.
export function CurrentPeriodLoader({month, currency}: {month: string; currency: string}) {
  const [result, setResult] = useState<{month: string; data: IntelligenceData} | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api.intelligence(month).then(data => {if (active) {setResult({month, data}); setError("");}})
      .catch((e: unknown) => {if (active) setError(errorMessage(e));});
    return () => {active = false;};
  }, [month]);
  const current = result?.month === month ? result.data.currencies.find(c => c.currency === currency) : null;
  return error ? <p className="notice" role="alert">Current-period facts: {error}</p> : current
    ? <CurrentPeriodFacts data={current} month={month} />
    : result?.month === month ? <p className="notice">No {currency} activity in {monthLabel(month)}.</p> : <p className="hint">Reading current-period facts…</p>;
}

export function CurrentPeriodFacts({data, month, showTotals = true}: {
  data: IntelligenceCurrency; month: string; showTotals?: boolean;
}) {
  const b = data.behaviour;
  if (!data.totals.transaction_count) return <p className="notice">No {data.currency} activity in {monthLabel(month)}.</p>;
  return <section className="current-period panel" aria-label="Current-month facts">
    <div className="panel-heading"><div><p className="page-kicker">Current month · {monthLabel(month)} · {data.currency}</p><h2>Here’s what we know now</h2></div></div>
    <dl className="movement-grid">
      {showTotals && <><div><dt>Income</dt><dd>{amount(data.totals.income, data.currency)}</dd></div><div><dt>Outflow</dt><dd>{amount(data.totals.outflow, data.currency)}</dd></div><div><dt>Net cash flow</dt><dd>{amount(data.totals.net_cash_flow, data.currency)}</dd></div></>}
      <div><dt>Spending</dt><dd>{amount(data.totals.spending, data.currency)}</dd></div>
      <div><dt>Transactions</dt><dd>{data.totals.transaction_count}</dd></div>
      <div><dt>Purchase frequency</dt><dd>{b.spending_count} purchases</dd><p>Across {b.active_spending_days} observed spending days</p></div>
      <div><dt>Cash withdrawn</dt><dd>{amount(data.totals.cash_out, data.currency)}</dd></div>
      <div><dt>Transfers out / in</dt><dd>{amount(data.totals.transfers_out, data.currency)} / {amount(b.transfer_inflows, data.currency)}</dd></div>
      <div><dt>Refund / reimbursement signals</dt><dd>{amount(b.return_inflows, data.currency)}</dd></div>
    </dl>
    <div className="mapping-fields">{[
      {label:"Category composition", rows:data.categories},
      {label:"Merchant composition", rows:b.top_spending_merchants},
    ].map(group => <div key={group.label}><h3>{group.label}</h3><ol className="composition-ranks">{group.rows.slice(0,5).map(row => <li key={row.name ?? "unknown"}><div><strong>{row.name ?? "Unknown merchant"}</strong><div className="composition-bar" aria-hidden="true" style={{width:`${row.share_percent ?? 0}%`}} /></div><span>{amount(row.amount,data.currency)}<small>{row.share_percent ?? "0"}% · {row.transaction_count} purchases</small></span></li>)}</ol>{!group.rows.length && <p>No purchases in this period.</p>}</div>)}</div>
    <h3>Largest purchases</h3><ol className="purchase-list">{b.largest_purchases.map(row => <li key={row.identifier}><div><Link href={`/app/transactions/${row.identifier}`}>{row.merchant ?? row.category}</Link><p>{dateLabel(row.day)}</p></div><strong>{amount(row.amount,data.currency)}</strong></li>)}</ol>
    <p className="hint">Observed activity, not an account balance. Spending excludes cash and transfers; refunds are shown separately. Imported months may be partial.</p>
  </section>;
}
