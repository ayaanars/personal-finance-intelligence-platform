"use client";
import Link from "next/link";
import { UnusualActivity } from "./unusual";
import { Relationships } from "./relationships";
import { useEffect, useState } from "react";
import { api, displayMoney, errorMessage } from "@/lib/api";
import type { IntelligenceCurrency, IntelligenceData } from "@/lib/analytics";
import { useIntelligencePeriod } from "./intelligence-period";
import { amount, monthLabel, LineChart } from "./intelligence-charts";
import { ChangeHero, InsightFeed, BaselineSnapshot, RecurringSnapshot } from "./intelligence-stories";
import { TrendsExplorer } from "./intelligence-trends";
import { RecurringCommitments, YourNormal } from "./overview-history";
import { BehaviourStory } from "./overview-intelligence";
export type IntelligenceArea = "overview" | "insights" | "trends" | "recurring" | "behaviour";
const descriptions = { overview: "The month. The movement. The bigger picture.", insights: "The important changes, with the evidence behind them.", trends: "Zoom out. Find your patterns over time.", recurring: "The payments that keep coming back.", behaviour: "Explore the rhythm behind your spending." };
export function Overview() { return <IntelligencePage page="overview"/>; }
export function IntelligencePage({ page }: {
    page: IntelligenceArea;
}) {
    const { month, setMonth, currency, setCurrency } = useIntelligencePeriod();
    const [data, setData] = useState<IntelligenceData | null>(null);
    const [busy, setBusy] = useState(true);
    const [error, setError] = useState("");
    const [revision, setRevision] = useState(0);
    useEffect(() => { let active = true; api.intelligence(month).then(result => { if (active)
        setData(result); }).catch((e: unknown) => { if (active)
        setError(errorMessage(e)); }).finally(() => { if (active)
        setBusy(false); }); return () => { active = false; }; }, [month, revision]);
    function load(next?: string) { setBusy(true); setError(""); setMonth(next); setRevision(v => v + 1); }
    const c = data?.currencies.find(item => item.currency === currency) ?? data?.currencies[0];
    const selected = month ?? data?.month ?? "";
    const months = [...new Set([...(data?.available_months ?? []), ...(selected ? [selected] : [])])].sort().reverse();
    const title = page[0].toUpperCase() + page.slice(1);
    return <div className={`intelligence-page area-${page}`}>
  <header className="intelligence-heading"><div><p className="page-kicker">Your financial perspective</p><h1>{title}</h1><p>{descriptions[page]}</p></div>
   <div className="period-controls">{months.length > 0 && <div><label htmlFor="overview-month">Month</label><select aria-label="Month" id="overview-month" value={selected} disabled={busy} onChange={e => load(e.target.value)}>{months.map(m => <option key={m} value={m}>{monthLabel(m)}</option>)}</select></div>}<button className="refresh-button" disabled={busy} aria-label={`Refresh ${title}`} onClick={() => load(month)}>↻</button></div>
  </header>
  {busy ? <div className="overview-skeleton" role="status" aria-label="Loading your financial overview"><span>Reading your imported activity…</span><div /><div /><div /></div> : error ? <section className="empty"><h2>Let’s reconnect to your history</h2><p role="alert">{error}</p><button onClick={() => load(month)}>Retry {title}</button></section> : data && c ? <>
   <div className="period-strip"><span>{data.month ? monthLabel(data.month) : "Imported activity"} <small> / {c.totals.transaction_count} transactions</small></span><div className="currency-picker" role="group" aria-label="Currency">{data.currencies.map(item => <button key={item.currency} aria-pressed={item.currency === c.currency} onClick={() => setCurrency(item.currency)}>{item.currency}</button>)}</div></div>
   <div className="intelligence-content" key={`${data.month}-${c.currency}-${page}`}>
    {c.comparison.state === "no_activity" && <p className="notice" role="status">No {c.currency} activity in the selected month. Earlier observations are shown without a current comparison.</p>}
    {page === "overview" ? <><UnusualActivity compact selectedMonth={data.month ?? undefined} selectedCurrency={c.currency}/><ExecutiveStory data={c}/></> : page === "insights" ? <><Relationships compact selectedMonth={data.month ?? undefined} selectedCurrency={c.currency}/><InsightFeed data={c}/><ChangeHero data={c} expanded/></> : page === "trends" ? <><TrendsExplorer data={c} month={data.month!}/><YourNormal data={c}/></> : page === "recurring" ? <RecurringCommitments data={c}/> : <><BehaviourStory data={c}/><Composition data={c}/></>}
   </div>
   <details className="method-disclosure"><summary>About this history · {c.baselines.observed_months} observed {c.baselines.observed_months === 1 ? "month" : "months"} · {c.currency} only</summary><p>{data.coverage_note}</p><p>Currencies are never combined or converted. Spending excludes Transfers and Cash / ATM; positive returns do not reduce gross spending. This is imported activity, not an account balance.</p><Link href="/app/import">Build your history</Link></details>
  </> : <section className="overview-empty"><h2>{data?.available_months.length ? "No imported activity in this window" : "Import your first statement to begin."}</h2><p>One month reveals where your money went. More history reveals what changes.</p><Link className="button primary" href="/app/import">Import statement</Link></section>}
 </div>;
}
function ExecutiveStory({ data }: {
    data: IntelligenceCurrency;
}) {
    return <>
  <dl className="financial-state">{([['Income', 'income'], ['Outflow', 'outflow'], ['Net cash flow', 'net_cash_flow']] as const).map(([label, key]) => { const change = data.comparison.metrics.find(r => r.name === key); return <div key={key} className={key === 'net_cash_flow' ? 'net-state' : ''}><dt>{label}</dt><dd>{amount(data.totals[key], data.currency)}</dd><p>{change ? `${displayMoney(change.delta, data.currency)} vs previous month` : "Comparison needs both months"}</p></div>; })}</dl>
  <ChangeHero data={data}/>
  <div className="executive-grid"><BaselineSnapshot data={data}/><section className="trend-snapshot panel"><div className="panel-heading"><h2>Recent direction</h2><Link href="/app/trends">Explore trends ↗</Link></div><LineChart points={data.trend.map(p => ({ month: p.month, value: p.totals.spending }))} currency={data.currency} label="Gross spending" compact/></section><RecurringSnapshot data={data}/><section className="panel observations-snapshot"><div className="panel-heading"><h2>Worth a closer look</h2><Link href="/app/insights">All insights ↗</Link></div><InsightFeed data={data} compact/></section></div>
 </>;
}
function Composition({ data }: {
    data: IntelligenceCurrency;
}) { const [view, setView] = useState<'categories' | 'merchants'>('categories'); const rows = view === 'categories' ? data.categories : data.behaviour.top_spending_merchants; return <section className="panel composition-explorer"><div className="panel-heading"><h2>Spending concentration</h2><div className="segmented" role="group" aria-label="Composition"><button aria-pressed={view === 'categories'} onClick={() => setView('categories')}>Categories</button><button aria-pressed={view === 'merchants'} onClick={() => setView('merchants')}>Merchants</button></div></div><ol className="composition-ranks">{rows.map((r, i) => <li key={r.name ?? 'unknown'}><span className="rank-number">{String(i + 1).padStart(2, '0')}</span><div><strong>{r.name ?? 'Unknown merchant'}</strong><div className="composition-bar" aria-hidden="true" style={{ width: `${r.share_percent ?? 0}%` }}/></div><strong>{amount(r.amount, data.currency)}<small>{r.share_percent ?? '0'}% · {r.transaction_count} purchases</small></strong></li>)}</ol>{!rows.length && <p>No spending in this month.</p>}</section>; }
