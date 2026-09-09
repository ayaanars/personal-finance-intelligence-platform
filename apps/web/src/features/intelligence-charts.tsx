"use client";
import { useId, useState } from "react";
import { displayMoney } from "@/lib/api";
export const amount = (value: string, currency: string) => displayMoney(value, currency).replace(/^\+/, "");
export function monthLabel(month: string) { const [year, m] = month.split("-"); return `${["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][Number(m) - 1]} ${year}`; }
export type PlotPoint = {
    month: string;
    value: string | null;
};
// Exact decimal integers determine geometry. Only bounded pixel coordinates become numbers.
export const decimalUnits = (value: string) => BigInt(value.replace(".", ""));
export function chartGeometry(points: PlotPoint[]) {
    const values = points.flatMap(p => p.value === null ? [] : [decimalUnits(p.value)]);
    const low = values.reduce((a, b) => b < a ? b : a, BigInt(0));
    const high = values.reduce((a, b) => b > a ? b : a, BigInt(0));
    const span = high - low || BigInt(1);
    const y = (v: bigint) => 184 - Number((v - low) * BigInt(14400) / span) / 100;
    return { zero: y(BigInt(0)), points: points.map((p, i) => ({ x: 32 + i * 576 / Math.max(1, points.length - 1), y: p.value === null ? null : y(decimalUnits(p.value)) })) };
}
export function LineChart({ points: observations, currency, label, compact = false }: {
    points: PlotPoint[];
    currency: string;
    label: string;
    compact?: boolean;
}) {
    // Insert explicit gaps so a missing calendar month cannot appear as continuous history.
    const first = observations[0]?.month;
    const last = observations.at(-1)?.month;
    const monthIndex = (m: string) => Number(m.slice(0, 4)) * 12 + Number(m.slice(5)) - 1;
    const points: PlotPoint[] = first && last ? Array.from({ length: monthIndex(last) - monthIndex(first) + 1 }, (_, i) => { const n = monthIndex(first) + i; const m = `${String(Math.floor(n / 12)).padStart(4, '0')}-${String(n % 12 + 1).padStart(2, '0')}`; return observations.find(p => p.month === m) ?? { month: m, value: null }; }) : [];
    const [active, setActive] = useState<number | null>(null);
    const id = useId();
    const geometry = chartGeometry(points);
    const selected = points[active ?? points.length - 1];
    const segments: string[] = [];
    let segment = "";
    geometry.points.forEach(p => { if (p.y === null) {
        if (segment)
            segments.push(segment);
        segment = "";
    }
    else
        segment += `${segment ? " L" : "M"}${p.x},${p.y}`; });
    if (segment)
        segments.push(segment);
    return <figure className={`line-chart ${compact ? "compact" : ""}`} aria-labelledby={id}>
  <figcaption id={id}><span>{label}</span><strong>{selected?.value != null ? amount(selected.value, currency) : "No observation"}</strong><small>{selected ? monthLabel(selected.month) : "No history"}</small></figcaption>
  {points.some(p => p.value !== null) ? <><svg viewBox="0 0 640 220" role="img" aria-label={`${label} over imported months. Exact values follow below.`}>
   {[40, 88, 136, 184].map(y => <line key={y} x1="32" x2="608" y1={y} y2={y} className="chart-gridline"/>)}
   <line x1="32" x2="608" y1={geometry.zero} y2={geometry.zero} className="chart-zero"/>
   {segments.map((d, i) => <path key={i} d={d} className="chart-line"/>)}
   {geometry.points.map((p, i) => p.y === null ? null : <g key={points[i].month}><circle cx={p.x} cy={p.y} r={active === i ? 7 : 4} className="chart-dot"/><text x={p.x} y="214" textAnchor="middle">{monthLabel(points[i].month).slice(0, 3)}</text></g>)}
  </svg><div className="chart-periods" aria-label="Explore chart values">{points.map((p, i) => <button key={p.month} aria-label={`${monthLabel(p.month)}: ${p.value === null ? "No observation" : amount(p.value, currency)}`} aria-pressed={active === i} onFocus={() => setActive(i)} onMouseEnter={() => setActive(i)} onClick={() => setActive(i)}>{monthLabel(p.month).slice(0, 3)}<span>{p.value === null ? "No data" : amount(p.value, currency)}</span></button>)}</div></> : <p className="history-message">No observations for this selection.</p>}
  {!compact && <p className="chart-note">Missing observations break the line. Imported months may be partial. Select or focus a month for its exact value.</p>}
 </figure>;
}
