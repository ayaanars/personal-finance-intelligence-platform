"use client";
import Link from "next/link";
import { CurrentPeriodLoader } from "./current-period";
import { useEffect, useId, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { monthLabel } from "@/lib/dates";
import type { RelationshipData, RelationshipsData } from "@/lib/relationships";
import { amount, decimalUnits, LineChart } from "./intelligence-charts";
import { useIntelligencePeriod } from "./intelligence-period";
function Scatter({ item, currency }: {
    item: RelationshipData;
    currency: string;
}) {
    const [active, setActive] = useState(item.points.length - 1);
    const id = useId();
    const xs = item.points.map(p => decimalUnits(p.x));
    const ys = item.points.map(p => decimalUnits(p.y));
    const minimum = (v: bigint[]) => v.reduce((a, b) => a < b ? a : b);
    const maximum = (v: bigint[]) => v.reduce((a, b) => a > b ? a : b);
    const x0 = minimum(xs), x1 = maximum(xs), y0 = minimum(ys), y1 = maximum(ys);
    const coordinate = (value: bigint, low: bigint, high: bigint) => Number((value - low) * BigInt(10000) / (high - low || BigInt(1))) / 10000;
    const point = item.points[active];
    return <figure className="relationship-scatter" aria-labelledby={id}>
    <figcaption id={id}><strong>{point ? monthLabel(point.month) : "Observed months"}</strong><span>{item.x_label}: {point && amount(point.x, currency)} · {item.y_label}: {point && amount(point.y, currency)}</span></figcaption>
    <svg viewBox="0 0 520 260" role="img" aria-label={`${item.x_label} horizontally, ${item.y_label} vertically. Each dot is one observed month; exact values follow below.`}>
      {[35, 95, 155, 215].map(y => <line key={y} x1="40" x2="490" y1={y} y2={y} className="chart-gridline"/>)}
      <text x="40" y="20">{item.y_label} ↑</text>
      {item.points.map((p, i) => <circle key={p.month} cx={40 + coordinate(xs[i], x0, x1) * 450} cy={215 - coordinate(ys[i], y0, y1) * 180} r={i === active ? 8 : 5} className={i === active ? "selected" : ""}><title>{monthLabel(p.month)}: {amount(p.x, currency)} / {amount(p.y, currency)}</title></circle>)}
      <text x="40" y="248">{amount(item.points[xs.indexOf(x0)].x, currency)}</text><text x="490" y="248" textAnchor="end">{amount(item.points[xs.indexOf(x1)].x, currency)}</text>
    </svg><p className="chart-note">Horizontal: {item.x_label}. Vertical range: {amount(item.points[ys.indexOf(y0)].y, currency)} to {amount(item.points[ys.indexOf(y1)].y, currency)}.</p>
    <div className="relationship-months" role="group" aria-label={`Explore ${item.x_label} months`}>{item.points.map((p, i) => <button key={p.month} aria-pressed={active === i} onClick={() => setActive(i)} onFocus={() => setActive(i)}>{monthLabel(p.month)}</button>)}</div>
  </figure>;
}
function RelationshipCard({ item, currency, rank }: {
    item: RelationshipData;
    currency: string;
    rank: number;
}) {
    const [view, setView] = useState("scatter");
    const evolution = item.evolution;
    const direction = (value: string) => value === "together" ? "Moved together" : value === "opposite" ? "Moved in opposite directions" : "No clear pattern";
    return <article className="relationship-card">
    <header><span className="rank-number">{String(rank).padStart(2, "0")}</span><div><p className="page-kicker">{item.sample_count} observed {item.code === "dining_change_net" ? "monthly changes" : "months"} · {currency}</p><h2>{item.x_label} <span>&</span> {item.y_label}</h2></div><span className="relationship-direction">{item.direction === "together" ? "↗ ↗ Together" : "↗ ↘ Opposite"}</span></header>
    <p className="relationship-interpretation">{item.interpretation}</p>
    <div className="relationship-body"><div><div className="segmented" role="group" aria-label={`View ${item.x_label}`}><button aria-pressed={view === "scatter"} onClick={() => setView("scatter")}>Compare months</button><button aria-pressed={view === "trends"} onClick={() => setView("trends")}>Paired trends</button></div>
      {view === "scatter" ? <Scatter item={item} currency={currency}/> : <div className="relationship-trends"><LineChart points={item.points.map(p => ({ month: p.month, value: p.x }))} currency={currency} label={item.x_label} compact/><LineChart points={item.points.map(p => ({ month: p.month, value: p.y }))} currency={currency} label={item.y_label} compact/><p className="chart-note">Each chart has its own labeled scale. Gaps remain visible.</p></div>}
    </div><div className="relationship-comparison"><h3>Compare the two groups</h3><p>{item.x_label} above its median of {amount(item.median_x, currency)}</p><strong>{amount(item.higher.y_mean, currency)}</strong><span>Average {item.y_label.toLowerCase()} · {item.higher.months.length} months</span><hr /><p>Other observed months</p><strong>{amount(item.other.y_mean, currency)}</strong><span>Average {item.y_label.toLowerCase()} · {item.other.months.length} months</span></div></div>
    <p className="relationship-caveat">{item.caveat}</p>
    <details><summary>History, methodology & how the relationship changed</summary>
      <p>Across {item.months.map(monthLabel).join(" · ")}. Descriptive Pearson r: {item.coefficient}. This is an association, not a probability, confidence level or evidence of causation.</p>
      <p>At least six observations, |r| ≥ 0.65, and the same direction with |r| ≥ 0.35 after removing any single observation. Groups split strictly above the median versus at/below it; each needs at least three months. These screening thresholds do not establish statistical certainty.</p>
      {evolution ? <div className="relationship-evolution"><div><h3>Earlier {evolution.earlier_months.length} observations</h3><strong>{direction(evolution.earlier_direction)}</strong><p>{evolution.earlier_months.map(monthLabel).join(" · ")}</p></div><div><h3>Recent six observations</h3><strong>{direction(evolution.recent_direction)}</strong><p>{evolution.recent_months.map(monthLabel).join(" · ")}</p></div><p>This split is descriptive, not a statistically established change.</p></div> : <p>Twelve usable observations unlock an earlier/recent comparison. No change in the relationship is inferred yet.</p>}
      <div className="table-scroll"><table><caption>Monthly evidence · {currency}</caption><thead><tr><th>Month</th><th>{item.x_label}</th><th>{item.y_label}</th><th>Group</th></tr></thead><tbody>{item.points.map(p => <tr key={p.month}><th>{monthLabel(p.month)}{p.previous_month && <small> vs {monthLabel(p.previous_month)}</small>}</th><td>{amount(p.x, currency)}</td><td>{amount(p.y, currency)}</td><td>{item.higher.months.includes(p.month) ? "Above median" : "Other"}</td></tr>)}</tbody></table></div>
    </details>
  </article>;
}
export function Relationships({ compact = false, selectedMonth, selectedCurrency }: {
    compact?: boolean;
    selectedMonth?: string;
    selectedCurrency?: string;
}) {
    const period = useIntelligencePeriod();
    const month = selectedMonth ?? period.month;
    const [result, setResult] = useState<{
        month?: string;
        data: RelationshipsData;
    } | null>(null);
    const [error, setError] = useState("");
    const [revision, setRevision] = useState(0);
    useEffect(() => {
        let active = true;
        api.relationships(month).then(data => { if (active) {
            setResult({ month, data });
            setError("");
        } }).catch((e: unknown) => { if (active)
            setError(errorMessage(e)); });
        return () => { active = false; };
    }, [month, revision]);
    const data = result?.month === month ? result?.data ?? null : null;
    const c = data?.currencies.find(c => c.currency === (selectedCurrency ?? period.currency)) ?? (selectedCurrency ? undefined : data?.currencies[0]);
    if (compact)
        return <section className="panel relationship-preview"><p className="page-kicker">Across your history</p>{c?.items[0] && !error && <><h2>{c.items[0].interpretation}</h2><p>{c.items[0].sample_count} observations · {c.currency} · Association only</p></>}<Link href="/app/relationships">Explore longer-term relationships ↗</Link></section>;
    return <div className="intelligence-page area-relationships"><header className="intelligence-heading"><div><p className="page-kicker">A longer perspective</p><h1>Relationships</h1><p>What tends to move together in your history.</p></div><div className="period-controls"><div><label htmlFor="relationship-month">Through month</label><select id="relationship-month" aria-label="Through month" value={month ?? data?.month ?? ""} onChange={e => { setError(""); period.setMonth(e.target.value); }}>{[...new Set([...(data?.available_months ?? result?.data.available_months ?? []), ...(month ? [month] : [])])].sort().reverse().map(m => <option key={m} value={m}>{monthLabel(m)}</option>)}</select></div><button className="refresh-button" aria-label="Refresh relationships" onClick={() => { setResult(null); setError(""); setRevision(r => r + 1); }}>↻</button></div></header>
    {error ? <section className="empty"><p role="alert">{error}</p><button onClick={() => { setError(""); setRevision(r => r + 1); }}>Retry</button></section> : !data ? <p role="status">Comparing your observed months…</p> : !c ? <section className="overview-empty"><h2>More history reveals relationships</h2><p>Import at least six observed months to begin exploring associations.</p><Link href="/app/import">Import statement</Link></section> : <>
      <div className="period-strip"><span>{data.window_start && monthLabel(data.window_start)} – {data.month && monthLabel(data.month)}<small> / {c.observed_months.length} observed months</small></span><div className="currency-picker" role="group" aria-label="Currency">{data.currencies.map(row => <button key={row.currency} aria-pressed={c.currency === row.currency} onClick={() => period.setCurrency(row.currency)}>{row.currency}</button>)}</div></div>
      {data.month && <CurrentPeriodLoader key={data.month} month={data.month} currency={c.currency} />}
      <div className="relationship-intro"><strong>{c.items.length.toString().padStart(2, "0")}</strong><div><h2>{c.items.length ? "Patterns worth exploring" : "Let the evidence develop"}</h2><p>Five focused comparisons. Only supported associations appear.</p></div></div>
      {c.state !== "available" && <section className="notice history-developing"><h2>{c.state === "no_clear_relationship" ? "No clear relationship to highlight" : "More history is needed"}</h2><p>{c.state === "no_clear_relationship" ? "The observed dimensions may be too stable, weakly associated or sensitive to a single month. This does not prove that no relationship exists." : "At least six usable observations are needed before LedgerX can identify relationships. Missing months are not counted as zero."}</p></section>}
      <div className="relationship-list" key={`${data.month}-${c.currency}`}>{c.items.map((item, index) => <RelationshipCard key={item.code} item={item} currency={c.currency} rank={index + 1}/>)}</div>
      <details className="method-disclosure"><summary>Coverage & comparisons considered</summary><p>{data.coverage_note}</p><p>Ranked by absolute descriptive correlation, then observation count. Relationships can overlap and must not be added as independent effects.</p><p>{c.missing_months.length ? `Unobserved months: ${c.missing_months.map(monthLabel).join(" · ")}.` : "Each calendar month in this window has imported activity; completeness is not established."}</p><ul>{c.screening.map(s => <li key={s.code}>{s.code.replaceAll("_", " ")} · {s.sample_count} observations · {s.state.replaceAll("_", " ")}</li>)}</ul></details>
    </>}
  </div>;
}
