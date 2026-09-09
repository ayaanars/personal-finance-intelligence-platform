"use client";

import Link from "next/link";
import { useState } from "react";
import type { BaselineData, IntelligenceCurrency } from "@/lib/analytics";
import { displayMoney } from "@/lib/api";

const amount = (value: string, currency: string) => displayMoney(value, currency).replace(/^\+/, "");

function BaselineBand({ row, currency }: { row: BaselineData; currency: string }) {
  if (row.state !== "available") return <div className="baseline-empty">
    <h3>{row.state === "no_activity" ? "No selected-month activity" : "Your baseline needs more history"}</h3>
    <p>{row.state === "no_activity" ? "A comparison needs imported activity in this month." : "Use at least three consecutive prior months. A category also needs purchases in at least three reference months."}</p>
    <Link href="/app/import">Add more history</Link>
  </div>;
  return <>
    <div className="baseline-current"><div><span>{row.name} this month</span><strong>{amount(row.current!, currency)}</strong></div>
      <span className="range-status">{row.position === "above" ? "Above" : row.position === "below" ? "Below" : "Within"} the observed range</span>
    </div>
    <figure className="baseline-figure">
      <figcaption>Observed prior range: <strong>{amount(row.low!, currency)} to {amount(row.high!, currency)}</strong></figcaption>
      <div className="baseline-axis" aria-hidden="true">
        <span className="baseline-range" style={{left:`${row.low_scale}%`,right:`calc(100% - ${row.high_scale}%)`}} />
        <span className="baseline-mean" style={{left:`${row.mean_scale}%`}} />
        <span className="baseline-marker" style={{left:`${row.current_scale}%`}} />
      </div>
      <div className="band-key"><span>Shaded: observed range</span><span>Line: mean</span><span>Diamond: this month</span></div>
    </figure>
    <p className="baseline-delta">{displayMoney(row.delta!, currency)} vs the recent mean{row.relative_percent !== null ? ` (${row.relative_percent}%)` : ""}</p>
    <details className="baseline-evidence"><summary>How {row.name.toLowerCase()} compares</summary>
      <p>Recent mean {amount(row.mean!, currency)}. The selected month is excluded; missing calendar months break the reference run.</p>
      <dl>{row.months.map((month, index) => <div key={month}><dt>{month}</dt><dd>{amount(row.values[index], currency)}</dd></div>)}</dl>
      <p>Category totals absent from an otherwise observed month are zero imported spending, not proof of no spending. This month may be partial.</p>
    </details>
  </>;
}

export function YourNormal({ data }: { data: IntelligenceCurrency }) {
  const report = data.baselines;
  const [selection, setSelection] = useState("metric:Spending");
  const options = [...report.metrics, ...report.categories];
  const row = options.find((item) => `${item.kind}:${item.name}` === selection) ?? report.metrics[0];
  return <section className="normal-section" aria-labelledby="normal-title">
    <h2 id="normal-title">Your normal</h2><p>See this month beside your own recent history.</p>
    <div className="normal-grid">
      <div>
        <label htmlFor="baseline-selection">Compare with your history</label>
        <select id="baseline-selection" value={selection} onChange={(event) => setSelection(event.target.value)}>
          <optgroup label="Monthly activity">{report.metrics.map((item) => <option key={item.name} value={`metric:${item.name}`}>{item.name}</option>)}</optgroup>
          <optgroup label="Spending categories">{report.categories.map((item) => <option key={item.name} value={`category:${item.name}`}>{item.name}</option>)}</optgroup>
        </select>
        <BaselineBand row={row} currency={data.currency} />
      </div>
      <aside className="baseline-reference" aria-label="Reference history">
        <p className="reference-count"><strong>{report.prior_months.length}</strong> consecutive prior months</p>
        <dl>
          <div><dt>Recent mean</dt><dd>{row.mean ? amount(row.mean, data.currency) : "Insufficient history"}</dd></div>
          <div><dt>3-month average</dt><dd>{row.average_three ? amount(row.average_three, data.currency) : "Insufficient history"}</dd></div>
          <div><dt>6-month average</dt><dd>{row.average_six ? amount(row.average_six, data.currency) : "Needs six reference months"}</dd></div>
        </dl>
        <p>{report.method}</p>
      </aside>
    </div>
  </section>;
}

const reasons = {
  fewer_than_three_months: "Fewer than three consecutive observed charge months",
  multiple_charges: "Multiple charges in a month; a single recurring payment is ambiguous",
  timing_not_regular: "Charge dates are outside the 21-40-day interval",
  amounts_vary: "Amounts differ by more than 5% from their median",
};

export function RecurringCommitments({ data }: { data: IntelligenceCurrency }) {
  const [expanded, setExpanded] = useState(false);
  const r = data.recurring;
  return <section className="recurring-section" aria-labelledby="recurring-title">
    <h2 id="recurring-title">Recurring commitments</h2><p>Likely monthly patterns, with the evidence behind each one.</p>
    {r.state === "likely_recurring" ? <div className="recurring-grid">
      <div className="recurring-totals">
        <span>Estimated monthly pattern</span><strong>{amount(r.monthly_estimate, data.currency)}</strong>
        <p>{amount(r.annual_estimate, data.currency)} <span>annualized estimate</span></p>
        <p className="recurring-count">{r.payments.length} likely monthly {r.payments.length === 1 ? "pattern" : "patterns"}</p>
        <div className="recurring-composition">
          <h3>Of this month’s spending</h3>
          <div className="composition-strip" aria-hidden="true"><span style={{width:`${r.matched_share_percent ?? "0"}%`}} /></div>
          <dl><div><dt>Matched charges</dt><dd>{amount(r.matched_spending, data.currency)}</dd></div>
            <div><dt>Other spending</dt><dd>{amount(r.other_spending, data.currency)}</dd></div></dl>
          <p>Actual charges, not the median estimate. Other spending may contain undetected recurring payments.</p>
        </div>
      </div>
      <div><ol className="recurring-list">{r.payments.slice(0, expanded ? undefined : 5).map((payment) => <li key={payment.merchant}>
        <div className="recurring-payment-heading"><h3>{payment.merchant}</h3><strong>{amount(payment.typical_amount, data.currency)}<small> / month</small></strong></div>
        {payment.newly_qualified && <p className="new-pattern">Newly qualified this month</p>}
        <div className="composition-bar" aria-hidden="true" style={{width:`${payment.share_percent ?? "0"}%`}} />
        <details><summary>Why this looks recurring</summary><p>{payment.reason}</p>
          <ol className="recurring-evidence">{payment.evidence.map((entry) => <li key={entry.identifier}><Link href={`/app/transactions/${entry.identifier}`}>{entry.day}</Link><strong>{amount(entry.amount, data.currency)}</strong></li>)}</ol>
          <p>Median observed charge × 12 = {amount(payment.annual_estimate, data.currency)}. {payment.newly_qualified === null ? "More earlier history is needed to know when this pattern first qualified." : "Newly qualified means the previous rolling window did not meet these rules; it does not mean a new subscription."}</p>
        </details>
      </li>)}</ol>
        {r.payments.length > 5 && <button className="text-button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? "Show largest five" : "Show all recurring patterns"}</button>}
      </div>
    </div> : <div className="baseline-empty"><h3>{r.state === "no_activity" ? "No activity in this month" : r.state === "insufficient_history" ? "More history unlocks recurring patterns" : "No strong recurring pattern yet"}</h3>
      <p>Detection needs one eligible charge from the same known merchant in each of three consecutive months, with similar amounts and regular timing.</p>
      <Link href="/app/import">Import more history</Link>
    </div>}
    {r.candidates.length > 0 && <details className="recurring-candidates"><summary>Insufficient evidence: {r.candidates.length} merchant {r.candidates.length === 1 ? "example" : "examples"}</summary>
      <ul>{r.candidates.map((candidate) => <li key={candidate.merchant}><strong>{candidate.merchant}</strong><p>{reasons[candidate.reason]}</p></li>)}</ul>
    </details>}
    <p className="overview-note">{r.method}</p>
  </section>;
}

export function HistoryDepth({ data }: { data: IntelligenceCurrency }) {
  return <section className="history-depth" aria-labelledby="depth-title">
    <div><h2 id="depth-title">Your history is the foundation</h2><p>{data.baselines.observed_months} observed months in this seven-month window. {data.baselines.prior_months.length} consecutive prior months support comparison.</p></div>
    <details><summary>What more history unlocks</summary><p>Two adjacent months show changes. Three charge months can reveal recurring patterns. Three prior months plus this month can support a baseline; six prior months add a longer average. Imported activity does not establish complete statement coverage.</p></details>
    <Link href="/app/import">Add another statement</Link>
  </section>;
}
