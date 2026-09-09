"use client";
import { useEffect, useState } from "react";
import type { IntelligenceCurrency } from "@/lib/analytics";
import { api, errorMessage } from "@/lib/api";
import { LineChart, type PlotPoint } from "./intelligence-charts";
type Mode = 'spending' | 'income' | 'outflow' | 'net_cash_flow' | 'category' | 'merchant' | 'recurring';
const labels: Record<Mode, string> = { spending: 'Spending', income: 'Income', outflow: 'Outflow', net_cash_flow: 'Net cash flow', category: 'Category', merchant: 'Merchant', recurring: 'Recurring' };
function calendarMonths(month: string) { const [y, m] = month.split('-').map(Number); const end = y * 12 + m - 1; return Array.from({ length: 7 }, (_, i) => end - 6 + i).filter(n => n >= 12).map(n => `${String(Math.floor(n / 12)).padStart(4, '0')}-${String(n % 12 + 1).padStart(2, '0')}`); }
export function TrendsExplorer({ data, month }: {
    data: IntelligenceCurrency;
    month: string;
}) {
    const [mode, setMode] = useState<Mode>('spending');
    const [selection, setSelection] = useState('');
    const [windowSize, setWindowSize] = useState('7');
    const [history, setHistory] = useState<Record<string, IntelligenceCurrency | null> | null>(null);
    const [failure, setFailure] = useState('');
    const [revision, setRevision] = useState(0);
    const needsHistory = mode === 'category' || mode === 'merchant' || mode === 'recurring';
    useEffect(() => {
        if (!needsHistory)
            return;
        let active = true;
        // Fetch only when deep exploration is requested. No persisted cache, derived sums or new endpoint.
        const months = calendarMonths(month).filter(m => m !== month);
        Promise.all(months.map(async (m) => { const response = await api.intelligence(m); return [m, response.currencies.find(c => c.currency === data.currency) ?? null] as const; })).then(rows => { if (active)
            setHistory(Object.fromEntries([...rows, [month, data]])); }).catch((e: unknown) => { if (active)
            setFailure(errorMessage(e)); });
        return () => { active = false; };
    }, [needsHistory, month, data, revision]);
    const months = calendarMonths(month).slice(-Number(windowSize));
    const options = mode === 'category' ? [...new Set(Object.values(history ?? {}).flatMap(c => c?.categories.map(r => r.name ?? 'Other') ?? []))].sort() : mode === 'merchant' ? [...new Set(Object.values(history ?? {}).flatMap(c => c?.behaviour.top_spending_merchants.map(r => r.name ?? 'Unknown merchant') ?? []))].sort() : [];
    const name = options.includes(selection) ? selection : options[0] ?? '';
    const points: PlotPoint[] = months.map(m => {
        if (!needsHistory) {
            const point = data.trend.find(p => p.month === m);
            return { month: m, value: point ? point.totals[mode as 'spending' | 'income' | 'outflow' | 'net_cash_flow'] : null };
        }
        const c = history?.[m];
        if (!c || c.comparison.state === 'no_activity')
            return { month: m, value: null };
        if (mode === 'recurring')
            return { month: m, value: c.recurring.state === 'likely_recurring' ? c.recurring.monthly_estimate : null };
        const rows = mode === 'category' ? c.categories : c.behaviour.top_spending_merchants;
        return { month: m, value: rows.find(r => (r.name ?? 'Unknown merchant') === name)?.amount ?? null };
    });
    return <section className="panel trends-explorer" aria-labelledby="trend-title"><div className="panel-heading"><h2 id="trend-title">Your recent trends</h2><div><label htmlFor="trend-window">Window</label><select id="trend-window" value={windowSize} onChange={e => setWindowSize(e.target.value)}><option value="7">7 months</option><option value="3">3 months</option></select></div></div>
  <div className="segmented trend-modes" role="group" aria-label="Trend metric">{(Object.keys(labels) as Mode[]).map(m => <button key={m} aria-pressed={mode === m} onClick={() => { setMode(m); setSelection(''); }}>{labels[m]}</button>)}</div>
  {needsHistory && !history && !failure ? <p className="history-message" role="status">Reading historical observations…</p> : failure && needsHistory ? <div className="notice"><p role="alert">{failure}</p><button onClick={() => { setFailure(''); setRevision(v => v + 1); }}>Retry historical trends</button></div> : <>
   {options.length > 0 && <div className="trend-selector"><label htmlFor="trend-subject">{labels[mode]}</label><select id="trend-subject" value={name} onChange={e => setSelection(e.target.value)}>{options.map(o => <option key={o}>{o}</option>)}</select></div>}
   <LineChart key={`${mode}-${name}-${windowSize}`} points={points} currency={data.currency} label={mode === 'category' || mode === 'merchant' ? `${name || labels[mode]} spending` : mode === 'recurring' ? 'Estimated monthly recurring pattern' : labels[mode]}/>
   {mode === 'merchant' && <p className="chart-note">Available observations are limited to each month’s top five spending merchants. An absent merchant is unknown, not zero.</p>}
   {mode === 'category' && <p className="chart-note">An absent category is shown as no observation, not evidence of zero spending.</p>}
   {mode === 'recurring' && <p className="chart-note">Each month applies the existing three-charge-month rule. Missing estimates mean insufficient evidence, not zero commitments.</p>}
  </>}
 </section>;
}
