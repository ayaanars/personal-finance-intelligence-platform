"use client";
import { readableDates } from "@/lib/dates";
import Link from "next/link";
import { useState } from "react";
import type { IntelligenceCurrency, BaselineData } from "@/lib/analytics";
import { displayMoney } from "@/lib/api";
import { amount, monthLabel } from "./intelligence-charts";
export function ChangeHero({ data, expanded = false }: {
    data: IntelligenceCurrency;
    expanded?: boolean;
}) {
    const [kind, setKind] = useState<'categories' | 'merchants'>('categories');
    const [all, setAll] = useState(expanded);
    const c = data.comparison;
    const out = c.metrics.find(r => r.name === 'outflow');
    const net = c.metrics.find(r => r.name === 'net_cash_flow');
    const rows = kind === 'categories' ? c.categories : data.behaviour.merchant_changes;
    return <section className="change-stage" aria-labelledby="changes-title"><div className="change-title"><span className="section-symbol" aria-hidden="true">↗</span><div><h2 id="changes-title">What changed?</h2><p>{c.state === 'available' ? `Against ${monthLabel(c.previous_month)}` : 'Your story is just beginning'}</p></div>{!expanded && <Link href="/app/insights">Unpack the changes ↗</Link>}</div>
  {c.state === 'available' ? <div className="change-stage-grid"><div className="change-headline"><span className="metric-label">Outflow change</span><strong className="hero-number">{out ? displayMoney(out.delta, data.currency) : 'No comparison'}</strong><span className="delta-tag">{out?.percent != null ? `${out.percent}% vs previous month` : 'Imported activity'}</span>
   <div className="cash-bridge"><span>Net cash flow</span>{net ? <><div><strong>{amount(net.previous, data.currency)}</strong><span aria-label="to">→</span><strong>{amount(net.current, data.currency)}</strong></div><p>{displayMoney(net.delta, data.currency)} change</p></> : <p>No comparable net cash flow.</p>}</div>
   <p className="change-footnote">Spending drivers exclude cash and transfers. Net cash flow also reflects changes in inflows.</p>
  </div><div className="contribution-explorer"><div className="segmented" role="group" aria-label="Change drivers"><button aria-pressed={kind === 'categories'} onClick={() => setKind('categories')}>Categories</button><button aria-pressed={kind === 'merchants'} onClick={() => setKind('merchants')}>Merchants</button></div><h3>Spending drivers</h3><ol className="contribution-ranks">{rows.slice(0, all ? undefined : 4).map((r, i) => <li key={r.name}><div className="driver-label"><span className="rank-number">{String(i + 1).padStart(2, '0')}</span><strong>{r.name}</strong><span>{displayMoney(r.delta, data.currency)}</span></div><div className={`contribution-fill ${r.delta.startsWith('-') ? 'negative' : ''}`} aria-hidden="true" style={{ width: `${r.scale_percent}%` }}/><details><summary>Why {r.name} changed</summary><p>{amount(r.current, data.currency)} this month minus {amount(r.previous, data.currency)} previously. This is a change in imported {kind === 'categories' ? 'category' : 'merchant spending'} totals, not an inferred cause.</p></details></li>)}</ol>{!rows.length && <p>No spending drivers supported by these months.</p>}{rows.length > 4 && <button className="text-button" aria-expanded={all} onClick={() => setAll(!all)}>{all ? 'Show major drivers' : `Show all ${rows.length} drivers`}</button>}<p className="chart-note">Ranked by absolute change. Hatched decreases offset increases. Category and merchant views overlap.</p></div></div> : <div className="history-message"><h3>{c.state === 'no_activity' ? 'This month needs activity' : 'This month is a starting point'}</h3><p>You have enough data to understand this month. A direct comparison needs activity in both adjacent months.</p><Link href="/app/import">Add more history ↗</Link></div>}
 </section>;
}
export function BaselineVisual({ row, currency }: {
    row: BaselineData;
    currency: string;
}) { return row.state === 'available' ? <><div className="baseline-status">{row.position === 'above' ? 'Above' : row.position === 'below' ? 'Below' : 'Within'} the observed range</div><div className="snapshot-range"><span>Recent range</span><strong>{amount(row.low!, currency)} to {amount(row.high!, currency)}</strong></div><div className="baseline-axis" aria-hidden="true"><span className="baseline-range" style={{ left: `${row.low_scale}%`, right: `calc(100% - ${row.high_scale}%)` }}/><span className="baseline-mean" style={{ left: `${row.mean_scale}%` }}/><span className="baseline-marker" style={{ left: `${row.current_scale}%` }}/></div><div className="band-key"><span>Band: history</span><span>Line: mean</span><span>Diamond: current</span></div><p>{displayMoney(row.delta!, currency)} vs recent mean</p></> : <div className="history-message"><h3>{row.state === 'no_activity' ? 'No selected-month activity' : 'Your baseline needs more history'}</h3><p>At least three consecutive prior observed months are needed.</p></div>; }
export function BaselineSnapshot({ data }: {
    data: IntelligenceCurrency;
}) { const row = data.baselines.metrics[0]; return <section className="panel baseline-snapshot"><div className="panel-heading"><h2>Your normal</h2><Link href="/app/trends">Compare history ↗</Link></div><p className="metric-label">Spending this month</p><strong className="snapshot-number">{amount(data.totals.spending, data.currency)}</strong><BaselineVisual row={row} currency={data.currency}/></section>; }
export function RecurringSnapshot({ data }: {
    data: IntelligenceCurrency;
}) { const r = data.recurring; return <section className="panel recurring-snapshot"><div className="panel-heading"><h2>On repeat</h2><Link href="/app/recurring">Explore recurring ↗</Link></div>{r.state === 'likely_recurring' ? <><span className="metric-label">Estimated monthly pattern</span><strong className="snapshot-number">{amount(r.monthly_estimate, data.currency)}</strong><p>{amount(r.annual_estimate, data.currency)} annualized</p><div className="recurring-chips">{r.payments.slice(0, 3).map(p => <span key={p.merchant}>{p.merchant}</span>)}{r.payments.length > 3 && <span>+{r.payments.length - 3} more</span>}</div><small>{r.payments.length} likely monthly patterns · estimates, not confirmed obligations</small></> : <div className="history-message"><h3>{r.state === 'insufficient_history' ? 'More history unlocks recurring patterns' : r.state === 'no_activity' ? 'No selected-month activity' : 'No strong recurring pattern yet'}</h3><p>Three consecutive charge months help reveal what repeats.</p></div>}</section>; }
export function InsightFeed({ data, compact = false }: {
    data: IntelligenceCurrency;
    compact?: boolean;
}) {
    const baseline = data.baselines.metrics[0];
    // Presentation priority: personal context, attributed drivers, then aggregate changes.
    // No new significance threshold or inferred financial recommendation.
    const insights = [...data.insights].sort((a, b) => Number(b.subject !== null) - Number(a.subject !== null));
    return <div className={compact ? 'compact-insights' : 'insights-feed'}>
  {!compact && <div className="insight-intro"><span className="section-symbol" aria-hidden="true">✦</span><p>Personal context first. Then the drivers and the overall change. Every observation is backed by imported activity.</p></div>}
  {!compact && baseline.state === 'available' && <article className="insight-feature"><div><span className="insight-kind">Personal baseline</span><h2>Spending is {baseline.position} your recent range</h2><strong>{amount(baseline.current!, data.currency)}</strong><p>{displayMoney(baseline.delta!, data.currency)} vs the recent mean</p></div><div><BaselineVisual row={baseline} currency={data.currency}/><details><summary>Evidence / why this matters</summary><p>Compared with {baseline.months.length} consecutive prior observed months. The selected month is excluded. This shows deviation from your imported history, not financial health.</p></details><Link href="/app/trends">Explore your baseline ↗</Link></div></article>}
  <div className="insight-cards">{insights.slice(0, compact ? 2 : undefined).map((insight, i) => <article key={insight.code}><span className="insight-index">{String(i + 1).padStart(2, '0')}</span><div><span className="insight-kind">{insight.subject ?? insight.metric.replaceAll('_', ' ')}</span><h3>{readableDates(insight.text)}</h3>{!compact && <strong className="insight-value">{displayMoney(insight.delta, data.currency)}</strong>}<details><summary>See the calculation</summary><p>Selected month: {amount(insight.current, data.currency)}. Previous month: {amount(insight.previous, data.currency)}. Change: {displayMoney(insight.delta, data.currency)}.</p>{insight.total_delta !== null && <p>Total {insight.metric} change: {displayMoney(insight.total_delta, data.currency)}. {insight.contribution_percent !== null ? `${insight.contribution_percent}% contribution (individual change ÷ total change).` : 'No same-direction contribution is inferred.'} Category and merchant views overlap.</p>}</details>{!compact && <Link href={insight.subject ? '/app/behaviour' : '/app/trends'}>Explore {insight.subject ? 'behaviour' : 'trends'} ↗</Link>}</div></article>)}</div>
  {!insights.length && <p className="history-message">{data.comparison.state === 'available' ? 'No supported month-over-month change to highlight.' : 'More adjacent history will reveal the changes that matter.'}</p>}
 </div>;
}
