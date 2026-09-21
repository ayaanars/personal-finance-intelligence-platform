"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { dateLabel, monthLabel } from "@/lib/dates";
import type { Plan } from "@/lib/goals";
import { amount, decimalUnits } from "./intelligence-charts";
import { useIntelligencePeriod } from "./intelligence-period";
function ratio(value: string, target: string) {
    const v = decimalUnits(value), t = decimalUnits(target);
    return Number(v < BigInt(0) ? BigInt(0) : v >= t ? BigInt(100) : v * BigInt(10000) / t) / (v >= t ? 1 : 100);
}
function approximate(value: string, currency: string) {
    const units = decimalUnits(value);
    const whole = ((units < BigInt(0) ? -units : units) + BigInt(5000)) / BigInt(10000);
    return `≈ ${units < BigInt(0) && whole ? "−" : ""}${whole.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")} ${currency}`;
}
function ProjectionTrend({ actual, projected, target, elapsed, days }: {
    actual: string;
    projected: string;
    target: string;
    elapsed: number;
    days: number;
}) {
    const values = [BigInt(0), decimalUnits(actual), decimalUnits(projected), decimalUnits(target)];
    const low = values.reduce((a, b) => a < b ? a : b), high = values.reduce((a, b) => a > b ? a : b);
    const y = (v: string) => 90 - Number((decimalUnits(v) - low) * BigInt(7000) / (high - low || BigInt(1))) / 100;
    const x = 10 + 260 * elapsed / days;
    return <svg className="goal-trend" viewBox="0 0 300 112" aria-hidden="true">
      <line x1="10" x2="270" y1={y(target)} y2={y(target)} stroke="currentColor" opacity=".35"/>
      <path d={`M 10 ${y("0.0000")} L ${x} ${y(actual)}`} fill="none" stroke="currentColor" strokeWidth="2"/>
      <path d={`M ${x} ${y(actual)} L 270 ${y(projected)}`} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="4 4"/>
      <circle cx={x} cy={y(actual)} r="4" fill="currentColor"/>
      <text x="10" y="108">Month start</text><text x="270" y="108" textAnchor="end">Month end</text>
    </svg>;
}
export function Goals({ compact = false, selectedMonth, selectedCurrency }: {
    compact?: boolean;
    selectedMonth?: string;
    selectedCurrency?: string;
}) {
    const period = useIntelligencePeriod();
    const month = selectedMonth ?? period.month;
    const [result, setResult] = useState<{
        month?: string;
        data: Plan;
    } | null>(null);
    const [error, setError] = useState("");
    const [revision, setRevision] = useState(0);
    const [busy, setBusy] = useState(false);
    const [saved, setSaved] = useState("");
    useEffect(() => {
        let active = true;
        api.plan(month).then(data => {
            if (active) {
                setResult({ month, data });
                setError("");
            }
        }).catch((e: unknown) => {
            if (active)
                setError(errorMessage(e));
        });
        return () => { active = false; };
    }, [month, revision]);
    const data = result?.month === month ? result?.data ?? null : null;
    const currency = selectedCurrency || period.currency || data?.currencies[0]?.currency || "AED";
    const f = data?.currencies.find(c => c.currency === currency);
    const goals = data?.goals.filter(g => g.currency === currency) ?? [];
    async function remove(kind: string) {
        if (!data)
            return;
        setBusy(true);
        setError("");
        setSaved("");
        try {
            await api.removeGoal({ month: data.month, currency, kind });
            setSaved("Goal removed.");
            setRevision(r => r + 1);
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setBusy(false);
        }
    }
    async function save(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!data)
            return;
        const fields = new FormData(event.currentTarget);
        setBusy(true);
        setError("");
        setSaved("");
        try {
            await api.saveGoal({ month: data.month, currency, kind: String(fields.get("kind")), target: String(fields.get("target")), active: fields.get("active") === "on" });
            setSaved("Goal saved.");
            setRevision(r => r + 1);
        }
        catch (e) {
            setError(errorMessage(e));
        }
        finally {
            setBusy(false);
        }
    }
    if (compact) {
        const goal = goals.find(g => g.active);
        return <section className="panel goal-summary"><p className="page-kicker">Month-end outlook · {currency}</p>{!error && f?.projected_spending ? <><h2>{goal?.kind === "net_cash_flow" ? `${f.state === "historical" ? "Observed" : "Projected"} net cash flow` : `${f.state === "historical" ? "Observed" : "Projected"} spending`}</h2><strong>{f.state === "historical" ? amount(goal?.projected ?? f.projected_spending, currency) : approximate(goal?.projected ?? f.projected_spending, currency)}</strong>{goal && <p>{amount(goal.target, currency)} target · {goal.status}</p>}<p>{f.quality}</p>{f.insight && <p>{f.insight}</p>}</> : <p>{error || "Add current-month activity to see an estimate."}</p>}<Link href="/app/goals">Goals & Forecast →</Link></section>;
    }
    return <div className="intelligence-page area-goals"><header className="intelligence-heading"><div><p className="page-kicker">Your month ahead</p><h1>Goals & Forecast</h1><p>Where you are heading, and what is still to come.</p></div><div className="period-controls"><label>Month<select aria-label="Month" value={month ?? data?.month ?? ""} onChange={e => { period.setMonth(e.target.value); setSaved(""); }}>{data?.available_months.map(m => <option key={m} value={m}>{monthLabel(m)}</option>)}</select></label><button onClick={() => setRevision(r => r + 1)}>Refresh</button></div></header>
 {error && <p role="alert">{error}</p>}{saved && <p role="status">{saved}</p>}
 {!data ? !error && <p role="status">Loading your plan…</p> : <><div className="period-strip"><span>{monthLabel(data.month)}</span><div className="currency-picker" role="group" aria-label="Currency">{["AED", "USD", "EUR", "GBP"].map(c => <button key={c} aria-pressed={currency === c} onClick={() => period.setCurrency(c)}>{c}</button>)}</div></div>
 {f?.state === "estimate" && f.history_months < 3 && <p className="notice history-developing">Limited-history forecast · Current spending pace supports a simple month-end projection. Goal progress uses actual imported activity. No historical comparison is inferred.</p>}
 {f && <section className="panel"><p className="page-kicker">{f.quality} · {f.elapsed_days}/{f.days_in_month} calendar days · {f.history_months} usable prior months</p><dl className="financial-state">{[["Spending", f.projected_spending], ["Outflow", f.projected_outflow], ["Net cash flow", f.projected_net_cash_flow]].map(([label, value]) => <div key={label}><dt>{f.state === "historical" ? "Observed" : "Projected"} {label}</dt><dd>{value === null ? "Not available" : f.state === "historical" ? amount(value, currency) : approximate(value, currency)}</dd></div>)}</dl><p>Latest imported activity: {dateLabel(f.last_activity)} · {f.observed_span_days} days from first to last observed activity.</p><details><summary>What drives this estimate?</summary><p>{f.explanation}</p><p>Quality uses the observed date span, freshness and usable prior months. Imported dates do not prove complete coverage. Estimates are displayed to the nearest whole currency unit.</p></details>{f.insight && <p>{f.insight}</p>}</section>}
 {!f && <section className="panel"><h2>Set your first target</h2><p>Import activity in this currency to build a forecast. Your goal can be saved now.</p></section>}
 <div className="goal-grid">{goals.map(g => <article className="panel goal-card" key={g.kind}><p className="page-kicker">{g.kind === "spending" ? "Monthly spending target" : "Monthly net cash flow target"}</p><h2>{amount(g.target, currency)}</h2><span className="goal-status">{g.status}</span><div className="goal-track" role="img" aria-label={`Actual ${amount(g.actual, currency)}; projected ${g.projected ? approximate(g.projected, currency) : "unavailable"}; target ${amount(g.target, currency)}`}><span style={{ width: `${ratio(g.actual, g.target)}%` }}/>{g.projected && <i style={{ left: `${ratio(g.projected, g.target)}%` }}/>}</div><p>Solid: actual · Marker: projection (capped at target)</p><p>Actual <strong>{amount(g.actual, currency)}</strong> · Projected <strong>{g.projected ? f?.state === "historical" ? amount(g.projected, currency) : approximate(g.projected, currency) : "Unavailable"}</strong></p>{g.projected && f && <><ProjectionTrend actual={g.actual} projected={g.projected} target={g.target} elapsed={f.elapsed_days} days={f.days_in_month}/><p className="chart-note">Straight-line progress to date; dotted projection to month end. Horizontal line: target.</p></>}<p>Target at this point in the month: {approximate(g.pace_target, currency)}</p><details><summary>Edit goal</summary><form onSubmit={save} key={`${data.month}-${currency}-${g.target}-${g.active}`}><input type="hidden" name="kind" value={g.kind}/><label>Target amount<input name="target" aria-label={`Edit ${g.kind} target`} inputMode="decimal" pattern="[0-9]+(\.[0-9]{1,4})?" defaultValue={g.target} required/></label><label><input name="active" type="checkbox" defaultChecked={g.active}/> Active</label><button disabled={busy}>Save changes</button></form><details><summary>Remove goal</summary><p>Remove this target for {monthLabel(data.month)}? Imported activity is preserved.</p><button disabled={busy} onClick={() => void remove(g.kind)}>Confirm removal</button></details></details></article>)}</div>
 <section className="panel"><h2>Add or replace a monthly goal</h2><form className="goal-form" onSubmit={save} key={`${data.month}-${currency}`}><label>Goal<select name="kind"><option value="spending">Spending target</option><option value="net_cash_flow">Net cash flow target</option></select></label><label>Target · {currency}<input name="target" aria-label="Target amount" inputMode="decimal" pattern="[0-9]+(\.[0-9]{1,4})?" required/></label><label><input type="checkbox" name="active" defaultChecked/> Active</label><button disabled={busy}>{busy ? "Saving…" : "Save goal"}</button></form><p>Applies to {monthLabel(data.month)} only. Net cash flow is imported inflows minus all outflows, not account savings or balance.</p></section>
 {f && <section className="panel"><p className="page-kicker">Still expected this month</p><h2>{approximate(f.remaining_recurring, currency)}</h2><p>Likely recurring charges, not confirmed obligations. Overdue charges are excluded from the projection.</p>{f.commitments.length ? <ul className="goal-commitments">{f.commitments.map(c => <li key={c.merchant}><strong>{c.merchant}</strong><span>{c.state === "observed" ? amount(c.amount, currency) : approximate(c.amount, currency)}</span><span>{c.state === "observed" ? "Observed this month" : c.state === "overdue" ? "Expected date passed · not observed" : "Still expected"} · {dateLabel(c.expected_day)}</span></li>)}</ul> : <p>No recurring charges have enough prior evidence.</p>}</section>}
 <details className="method-disclosure"><summary>How goal status works</summary><p>Spending: off track when already above target, or both pace and projection exceed it. Net cash flow: off track when both progress and projection are below target. One unfavorable comparison means watch closely; otherwise on track. Straight-line progress is a planning reference, not a claim that income arrives evenly. Inactive goals are excluded from the Overview summary.</p></details></>}
 </div>;
}
