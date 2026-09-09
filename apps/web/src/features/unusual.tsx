"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { dateLabel, monthLabel } from "@/lib/dates";
import type { UnusualData } from "@/lib/unusual";
import { amount } from "./intelligence-charts";
import { useIntelligencePeriod } from "./intelligence-period";
export function UnusualActivity({ compact = false, selectedMonth, selectedCurrency }: {
    compact?: boolean;
    selectedMonth?: string;
    selectedCurrency?: string;
}) {
    const period = useIntelligencePeriod();
    const month = selectedMonth ?? period.month;
    const [result, setResult] = useState<{
        month?: string;
        data: UnusualData;
    } | null>(null);
    const [error, setError] = useState("");
    const [revision, setRevision] = useState(0);
    useEffect(() => {
        let active = true;
        api.unusual(month).then(data => { if (active) {
            setResult({ month, data });
            setError("");
        } })
            .catch((e: unknown) => { if (active)
            setError(errorMessage(e)); });
        return () => { active = false; };
    }, [month, revision]);
    const data = result?.month === month ? result?.data : null;
    const c = data?.currencies.find(item => item.currency === (selectedCurrency ?? period.currency)) ?? data?.currencies[0];
    if (compact)
        return <section className="unusual-summary panel"><span>{c ? `${c.total} unusual ${c.total === 1 ? "change" : "changes"} · ${c.currency}` : error ? "Unusual activity unavailable" : "Your unusual activity"}</span><Link href="/app/unusual">Explore unusual activity ↗</Link></section>;
    return <div className="intelligence-page area-unusual">
    <header className="intelligence-heading"><div><p className="page-kicker">Your history, in perspective</p><h1>Unusual activity</h1><p>What stands out. And the evidence behind it.</p></div>
      <div className="period-controls"><label>Month<select value={month ?? data?.month ?? ""} onChange={e => { setError(""); period.setMonth(e.target.value); }}>{[...new Set([...(data?.available_months ?? result?.data.available_months ?? []), ...(month ? [month] : [])])].sort().reverse().map(m => <option key={m} value={m}>{monthLabel(m)}</option>)}</select></label><button aria-label="Refresh unusual activity" onClick={() => { setError(""); setResult(null); setRevision(r => r + 1); }}>↻</button></div>
    </header>
    {error ? <section className="empty"><p role="alert">{error}</p><button onClick={() => { setError(""); setRevision(r => r + 1); }}>Retry</button></section> : !data ? <p role="status">Comparing your imported history…</p> : !c ? <section className="overview-empty"><h2>Build your personal history</h2><p>Import statements to reveal supported changes over time.</p><Link href="/app/import">Import statement</Link></section> : <>
      <div className="period-strip"><span>{data.month && monthLabel(data.month)}</span><div className="currency-picker" role="group" aria-label="Currency">{data.currencies.map(item => <button key={item.currency} aria-pressed={item.currency === c.currency} onClick={() => period.setCurrency(item.currency)}>{item.currency}</button>)}</div></div>
      <section className="unusual-lead"><strong>{c.total.toString().padStart(2, "0")}</strong><div><h2>{c.total === 0 ? "No supported changes to highlight" : c.total === 1 ? "Change worth a closer look" : "Changes worth a closer look"}</h2><p>Compared with {c.prior_months.length} prior months · {c.historical_purchases} reference purchases</p></div></section>
      {c.state !== "available" && <p className="notice">{c.state === "no_activity" ? "No imported activity in this month." : "Insufficient history for broad comparisons. Three consecutive prior months unlock personal baselines."}</p>}
      {c.historical_purchases < 20 && <p className="chart-note">Large-purchase, merchant novelty, merchant spending and frequency rules need 20 reference purchases across at least three months. Category and recurring evidence can still qualify independently.</p>}
      <ol className="unusual-list" key={`${data.month}-${c.currency}`}>{c.items.map((item, index) => <li className="unusual-card" key={item.identifier}>
        <div className="unusual-card-heading"><span className="rank-number">{String(index + 1).padStart(2, "0")}</span><div><h2>{item.subject}</h2><p>{item.day ? dateLabel(item.day) : data.month && monthLabel(data.month)}</p></div><span className={`unusual-severity ${item.severity.toLowerCase()}`}>{item.severity}</span></div>
        <div className="unusual-evidence">{item.evidence.map(e => { const value = (v: string) => e.unit === "money" ? amount(v, c.currency) : `${v.replace(/\.?0+$/, "")} purchases`; return <section key={e.code}><p className="metric-label">{e.code.replaceAll("_", " ")}</p><strong>{value(e.current)}</strong>{e.ratio && <span className="delta-tag">{e.ratio}× reference</span>}<p>{e.explanation}</p>{e.reference !== null && <div className="unusual-comparison"><div><span>Reference</span><b>{value(e.reference)}</b></div><div className="unusual-bar" aria-hidden="true"><i style={{ width: `${e.reference_scale}%` }}/></div><div><span>Current</span><b>{value(e.current)}</b></div><div className="unusual-bar current" aria-hidden="true"><i style={{ width: `${e.reference_scale && Number(e.reference_scale) === 100 && e.ratio ? Math.min(100, Number(e.ratio) * 100) : 100}%` }}/></div></div>}</section>; })}</div>
        <details><summary>Supporting history{item.ml_supported ? " · additional pattern support" : ""}</summary><p>{c.prior_months.map(monthLabel).join(" · ")}. Selected-month activity is excluded from reference comparisons. First observed means within imported history only.</p>{item.ml_supported && <p>A model fitted only to your earlier purchases also found this pattern unusual. Severity comes from the explained rules.</p>}<div className="unusual-links">{item.transaction_ids.map((id, i) => <Link key={id} href={`/app/transactions/${id}`}>View transaction {i + 1} ↗</Link>)}</div></details>
      </li>)}</ol>
      {!c.total && c.state === "available" && <section className="panel"><h2>No supported unusual changes to highlight</h2><p>This describes the available evidence; it does not guarantee that every transaction is expected.</p></section>}
      {c.total > c.items.length && <p>Showing the 100 highest-ranked observations of {c.total}.</p>}
      <details className="method-disclosure"><summary>How these comparisons work</summary><p>{data.coverage_note}</p><p>High: a purchase at least 6× its median, category/merchant spending or frequency at least 3× its mean, or a recurring amount change of at least 100%. Other qualifying observations are Notable. High items appear first, followed by evidence count, model support and relative change.</p><p>{c.ml_state === "active" ? "Additional pattern support is active." : c.ml_state === "unavailable" ? "Additional pattern support is unavailable. Deterministic rules remain active." : "Additional pattern support needs 100 prior purchases, three consecutive prior months and current purchases."} The model uses relative amount, day of month, weekday/weekend and daily purchase count. No probability or fraud score is inferred.</p></details>
    </>}
  </div>;
}
