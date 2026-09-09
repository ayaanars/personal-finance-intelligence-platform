"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, displayMoney, errorMessage } from "@/lib/api";
import type { IntelligenceCurrency as CurrencyOverview, IntelligenceData as OverviewData } from "@/lib/analytics";
import { BehaviourStory } from "./overview-intelligence";
import { HistoryDepth, RecurringCommitments, YourNormal } from "./overview-history";

function monthLabel(month: string) {
  const [year, value] = month.split("-");
  const names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  return `${names[Number(value) - 1]} ${year}`;
}

function amount(value: string, currency: string) {
  return displayMoney(value, currency).replace(/^\+/, "");
}

export function Overview() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [month, setMonth] = useState<string>();
  const [currency, setCurrency] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    api.intelligence(month).then((result) => {
      if (active) setData(result);
    }).catch((failure: unknown) => {
      if (active) setError(errorMessage(failure));
    }).finally(() => {
      if (active) setBusy(false);
    });
    return () => { active = false; };
  }, [month, revision]);

  function load(next?: string) {
    setBusy(true);
    setError("");
    setMonth(next);
    setRevision((value) => value + 1);
  }
  const activeCurrency = data?.currencies.find((item) => item.currency === currency) ?? data?.currencies[0];
  const selected = month ?? data?.month ?? "";
  const months = [...new Set([...(data?.available_months ?? []), ...(selected ? [selected] : [])])].sort().reverse();

  return (
    <div className="overview">
      <header className="overview-heading">
        <div>
          <p className="eyebrow">Your financial perspective</p>
          <h1>Overview</h1>
          <p>What happened. Where it went. What changed.</p>
        </div>
        <div className="overview-controls">
          {months.length > 0 && <div>
            <label htmlFor="overview-month">Month</label>
            <select id="overview-month" value={selected} disabled={busy} onChange={(event) => load(event.target.value)}>
              {months.map((value) => <option key={value} value={value}>{monthLabel(value)}</option>)}
            </select>
          </div>}
          <button className="text-button" disabled={busy} onClick={() => load(month)}>Refresh Overview</button>
        </div>
      </header>

      {busy ? <div className="overview-skeleton" role="status" aria-label="Loading your financial overview">
        <span>Reading your imported activity…</span><div /><div /><div />
      </div> : error ? <section className="empty">
        <h2>Let’s reconnect to your history</h2><p role="alert">{error}</p>
        <button onClick={() => load(month)}>Retry Overview</button>
      </section> : data && activeCurrency ? <>
        <div className="overview-context">
          <p>{monthLabel(data.month!)} <span>· Imported activity</span></p>
          <div className="currency-picker" role="group" aria-label="Currency">
            {data.currencies.map((item) => <button key={item.currency}
              aria-pressed={item.currency === activeCurrency.currency}
              onClick={() => setCurrency(item.currency)}>{item.currency}</button>)}
          </div>
        </div>
        {data.currencies.length > 1 && <p className="overview-note">Each currency tells its own story. Totals are never combined or converted.</p>}
        <CurrencyStory key={`${data.month}-${activeCurrency.currency}`} data={activeCurrency} />
        <section className="overview-method" aria-label="About these calculations">
          <h2>Read your history with context</h2>
          <p>{data.coverage_note}</p>
          <p>Income includes positive activity categorized Income. Net cash flow uses all inflows minus all outflows. Spending excludes Transfers and Cash / ATM. Refunds and reimbursements stay in other inflows and do not reduce gross spending. Unknown activity stays Other.</p>
          <Link href="/app/transactions">Review transactions and categories</Link>
        </section>
      </> : <section className="overview-empty">
        <p className="eyebrow">A clearer picture starts here</p>
        <h2>{data?.available_months.length ? "No imported activity in this window" : "Import your first statement to begin."}</h2>
        <p>{data?.available_months.length ? "Choose another month or import more history." : "One month reveals where your money went. Another begins to show how things are changing."}</p>
        <Link className="button primary" href="/app/import">Import statement</Link>
      </section>}
    </div>
  );
}

function CurrencyStory({ data }: { data: CurrencyOverview }) {
  const { currency, totals, comparison } = data;
  const comparable = comparison.state === "available";
  const [drivers, setDrivers] = useState(false);
  const [trendMetric, setTrendMetric] = useState<"spending" | "income" | "outflow">("spending");
  return <>
    {comparison.state === "no_activity" && <p className="notice" role="status">No {currency} activity in the selected month. Earlier imported months appear below; no comparison is inferred.</p>}
    <dl className="overview-summary">
      {([
        ["Income", "income", totals.income],
        ["Outflow", "outflow", totals.outflow],
        ["Net cash flow", "net_cash_flow", totals.net_cash_flow],
      ] as const).map(([label, metric, value]) => {
        const change = comparison.metrics.find((row) => row.name === metric);
        return <div key={metric} className={metric === "net_cash_flow" ? "summary-net" : ""}>
          <dt>{label}</dt><dd>{amount(value, currency)}</dd>
          <p>{change ? `${displayMoney(change.delta, currency)} vs previous month${change.percent !== null ? ` (${change.percent}%)` : ""}` : "Comparison needs activity in both months"}</p>
        </div>;
      })}
    </dl>
    <div className="overview-reconcile">
      <p>All inflows <strong>{amount(totals.inflows, currency)}</strong></p>
      <p>Other inflows <strong>{amount(totals.other_inflows, currency)}</strong></p>
      <p>{totals.transaction_count} transactions{data.observed_start ? ` · Observed ${data.observed_start} to ${data.observed_end}` : ""}</p>
    </div>

    <section className="overview-changes" aria-labelledby="changes-title">
      <div><h2 id="changes-title">What changed?</h2>
        <p>{comparable ? `Compared with ${monthLabel(comparison.previous_month)}, using imported activity.` : "More history brings more perspective."}</p>
      </div>
      {comparable && <div className="change-hero">
        <div className="change-before-after">{comparison.metrics.filter((row) => row.name === "outflow" || row.name === "net_cash_flow").map((row) => <div key={row.name}>
          <span>{row.name === "outflow" ? "Outflow change" : "Net cash flow change"}</span>
          <strong>{displayMoney(row.delta, currency)}</strong>
          <p>{amount(row.previous, currency)} <span aria-label="to">→</span> {amount(row.current, currency)}</p>
        </div>)}</div>
        <div className="change-drivers">
          <h3>Spending drivers</h3><p>Ranked by absolute change. Decreases offset increases.</p>
          <ol>{comparison.categories.slice(0, drivers ? undefined : 5).map((row) => <li key={row.name}>
            <div><span>{row.name}</span><strong>{displayMoney(row.delta, currency)}</strong></div>
            <div className={`driver-bar ${row.delta.startsWith("-") ? "decrease" : "increase"}`} aria-hidden="true" style={{ width: `${row.scale_percent}%` }} />
            <details><summary>Why {row.name} changed</summary><p>{amount(row.current, currency)} this month minus {amount(row.previous, currency)} previously. This is a change in imported category totals, not an inferred cause.</p></details>
          </li>)}</ol>
          {comparison.categories.length > 5 && <button className="text-button" aria-expanded={drivers} onClick={() => setDrivers(!drivers)}>{drivers ? "Show top five drivers" : "Show all drivers"}</button>}
        </div>
      </div>}
      {comparable ? data.insights.length ? <div className="insight-list">
        {data.insights.map((insight) => <article key={insight.code}>
          <p>{insight.text}</p>
          <details><summary>See the calculation</summary>
            <p>Selected month: {amount(insight.current, currency)}. Previous month: {amount(insight.previous, currency)}. Change: {displayMoney(insight.delta, currency)}.</p>
            {insight.total_delta !== null && <p>Total {insight.metric} change: {displayMoney(insight.total_delta, currency)}.{insight.contribution_percent !== null ? ` Contribution: ${insight.contribution_percent}% (individual change ÷ total change). Categories and merchants are overlapping views, not additive.` : " No same-direction contribution is inferred."}</p>}
          </details>
        </article>)}
      </div> : <p className="history-message">Outflow, net cash flow, category spending and merchant outflow are unchanged across these imported months.</p> : <div className="history-message">
        <h3>{comparison.state === "no_activity" ? "This month needs activity" : "This month is a starting point"}</h3>
        <p>{comparison.state === "no_activity" ? "Import activity for the selected month to compare it." : `You have enough data to understand this month. Import another month to start seeing changes over time. A direct comparison needs ${monthLabel(comparison.previous_month)} activity in ${currency}.`}</p>
        <Link href="/app/import">Add more history</Link>
      </div>}
    </section>

    <nav className="intelligence-nav" aria-label="Explore intelligence"><a href="#normal-title">Your normal</a><a href="#spending-title">Composition</a><a href="#trend-title">Trends</a><a href="#recurring-title">Recurring</a><a href="#behaviour-title">Behaviour</a></nav>
    <YourNormal data={data} />
    <div className="overview-detail-grid">
      <section aria-labelledby="spending-title" className="spending-section">
        <h2 id="spending-title">Where your money went</h2>
        <p className="section-intro">Gross spending <strong>{amount(totals.spending, currency)}</strong></p>
        {data.categories.length ? <ol className="category-list">
          {data.categories.map((row) => <li key={row.name}>
            <div><strong>{row.name}</strong><span>{row.transaction_count} {row.transaction_count === 1 ? "transaction" : "transactions"} · {row.share_percent}% of spending</span><div className="composition-bar" aria-hidden="true" style={{ width: `${row.share_percent ?? "0"}%` }} /></div>
            <strong>{amount(row.amount, currency)}</strong>
          </li>)}
        </ol> : <p className="history-message">No spending recorded for this month.</p>}
        <div className="spending-exclusions">
          <p>Transfer outflow <strong>{amount(totals.transfers_out, currency)}</strong></p>
          <p>Cash / ATM <strong>{amount(totals.cash_out, currency)}</strong></p>
          <span>Shown separately from spending. Cash withdrawals do not reveal where the cash was spent.</span>
        </div>
        {comparable && <details><summary>Category changes since {monthLabel(comparison.previous_month)}</summary>
          <ul className="category-deltas">{comparison.categories.map((row) => <li key={row.name}><span>{row.name}</span><span>{displayMoney(row.delta, currency)}{row.percent !== null ? ` (${row.percent}%)` : " · No percentage: prior value is zero"}</span></li>)}</ul>
        </details>}
      </section>
      <section aria-labelledby="trend-title" className="trend-section">
        <h2 id="trend-title">Your recent trends</h2>
        <p className="section-intro">Actual imported months in the seven-month window. Gaps are omitted, not treated as zero.</p>
        <div className="segmented" role="group" aria-label="Trend metric">{(["spending", "income", "outflow"] as const).map((metric) => <button key={metric} aria-pressed={trendMetric === metric} onClick={() => setTrendMetric(metric)}>{metric === "spending" ? "Spending" : metric === "income" ? "Income" : "Outflow"}</button>)}</div>
        <figure className="spending-trend">
          <figcaption>{trendMetric === "spending" ? "Gross spending" : trendMetric === "income" ? "Income" : "All outflow"} by month · {currency}</figcaption>
          <ol>{data.trend.map((point) => <li key={point.month}>
            <div><span>{monthLabel(point.month)}</span><strong>{amount(point.totals[trendMetric], currency)}</strong></div>
            <div className="trend-bar" aria-hidden="true" style={{ width: `${point[`${trendMetric}_scale_percent`]}%` }} />
          </li>)}</ol>
        </figure>
        <h2 className="merchant-heading" id="merchant-title">Top merchants by outflow</h2>
        <p className="section-intro">Includes all outflows, even Transfers and Cash / ATM. Positive adjustments are excluded.</p>
        {data.top_merchants.length ? <ol className="merchant-list" aria-labelledby="merchant-title">
          {data.top_merchants.map((row, index) => <li key={row.name ?? "unknown"}>
            <span className="merchant-rank" aria-hidden="true">{index + 1}</span>
            <div><strong>{row.name ?? "Unknown merchant"}</strong><span>{row.transaction_count} {row.transaction_count === 1 ? "transaction" : "transactions"} · {row.share_percent}% of outflow</span></div>
            <strong>{amount(row.amount, currency)}</strong>
          </li>)}
        </ol> : <p className="history-message">No merchant outflow in this month.</p>}
      </section>
    </div>
    <RecurringCommitments data={data} />
    <BehaviourStory data={data} />
    <HistoryDepth data={data} />
  </>;
}
