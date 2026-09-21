"use client";
import { dateLabel } from "@/lib/dates";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  api,
  ApiError,
  displayMoney,
  errorMessage,
  type ImportPreview,
  type RowPage,
  type ColumnMapping,
  type Inspection,
} from "@/lib/api";

export function UploadStatement() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [mapping, setMapping] = useState<ColumnMapping | null>(null);
  const [dateFormat, setDateFormat] = useState("");
  const [showMapping, setShowMapping] = useState(false);
  const [signConfirmed, setSignConfirmed] = useState(false);
  const [profileConfirmed, setProfileConfirmed] = useState(false);
  const stagedId = useRef<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [attempted, setAttempted] = useState(false);
  const key = useRef("");
  useEffect(() => {
    if (!file) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [file]);
  function edit(patch: Partial<ColumnMapping>) {
    if (busy || attempted || !mapping) return;
    setMapping({...mapping, ...patch});
    setInspection(value => value ? {...value, invalid_rows: null, samples: value.samples.map(row => ({...row, normalized: null}))} : value);
    setError("");
  }
  async function inspect(candidate: File) {
    if (busy || attempted) return;
    setError("");
    setInspection(null);
    setMapping(null);
    if (!candidate.name.toLowerCase().endsWith(".csv") || !candidate.size || candidate.size > 5 * 1024 * 1024) {
      setFile(null);
      setError("Choose a non-empty UTF-8 CSV no larger than 5 MiB.");
      return;
    }
    setFile(candidate);
    setBusy(true);
    key.current = crypto.randomUUID();
    stagedId.current = null;
    setSignConfirmed(false); setProfileConfirmed(false);
    try {
      const result = await api.inspect(candidate);
      setInspection(result);
      const s = result.suggestions;
      const split = !s.amount && !!s.debit && !!s.credit;
      setShowMapping(result.recognition.state === "needs_mapping");
      const recognized = result.recognition.mapping;
      const format = result.recognition.questions.includes("date_format") ? "" : recognized?.date_format ?? (result.date_formats.length === 1 ? result.date_formats[0] : "");
      setDateFormat(format);
      setMapping(recognized ?? {transaction_date: s.transaction_date ?? "", description: s.description ?? "",
        amount_mode: split ? "debit_credit" : "single", amount: split ? null : s.amount ?? null,
        debit: split ? s.debit : null, credit: split ? s.credit : null,
        currency: s.currency ?? null, fixed_currency: null,
        date_format: (format || "YYYY-MM-DD") as ColumnMapping["date_format"]});
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  async function preview() {
    if (!file || !mapping || !dateFormat) { setError("Select a date format before previewing."); return; }
    setBusy(true); setError("");
    try { setInspection(await api.inspect(file, mapping)); setShowMapping(false); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  async function stage() {
    if (!file || !mapping || busy || inspection?.invalid_rows !== 0) return;
    setBusy(true); setError(""); setAttempted(true);
    try {
      const result = await api.upload(file, key.current, mapping);
      stagedId.current = result.id;
      await api.finalize(result.id, result.id);
      setFile(null);
      router.push(`/app/import/${result.id}`);
    } catch (e) {
      setError(errorMessage(e));
      if (!stagedId.current && e instanceof ApiError && [400,401,403,413,415,422].includes(e.status)) setAttempted(false);
      setBusy(false);
    }
  }
  function selector(label: string, field: "transaction_date" | "description" | "amount" | "debit" | "credit" | "currency") {
    return <label>{label}<select aria-label={label} value={mapping?.[field] ?? ""} onChange={event => {
      edit({[field]: event.target.value || null, ...(field === "currency" ? {fixed_currency: null} : {})});
      if (field === "transaction_date") setDateFormat("");
    }}><option value="">Select a source column</option>{inspection?.headers.map(header => <option key={header} value={header}>{header}</option>)}</select></label>;
  }
  const questions = inspection?.recognition.questions ?? [];
  const needsAnswers = inspection?.recognition.state !== "recognized";
  return <>
    <div className="page-heading"><div><p className="eyebrow">Upload → Preview → Confirm import</p><h1>Import your statement.</h1><p>Review the column choices and normalized values before adding any transactions.</p></div></div>
    <section className="data-section">
      <h2>1. Upload CSV</h2>
      <label htmlFor="csv">Choose your statement</label>
      <input id="csv" type="file" accept=".csv,text/csv" disabled={busy || attempted} onChange={event => {if(event.target.files?.[0]) void inspect(event.target.files[0]);}} />
      <p className="hint">UTF-8, comma-separated CSV · 5 MiB · 25,000 rows. XLSX is not supported yet. Raw statement contents are not retained.</p>
      {error && <p role="alert" className="notice error">{error}</p>}
      {busy && <p role="status">Processing statement…</p>}
    </section>
    {inspection && mapping && <section className="data-section mapping-panel">
      <h2>{inspection.recognition.state === "recognized" ? inspection.recognition.source === "reviewed" ? "Mapping confirmed" : "Recognized automatically" : inspection.recognition.state === "needs_confirmation" ? "Needs confirmation" : "Needs mapping"}</h2>
      <p>{inspection.recognition.state === "recognized" ? inspection.recognition.profile_name ? `Applied saved mapping: ${inspection.recognition.profile_name}. Review the preview before confirming.` : inspection.recognition.source === "reviewed" ? "Your mapping has been checked. Review the preview before confirming." : "We recognized this statement format. Review the preview before confirming." : "We need a little more information to interpret this statement safely."}</p>
      <p className="hint">Date: {mapping.transaction_date || "Not selected"} · Description: {mapping.description || "Not selected"} · {mapping.amount_mode === "single" ? `Signed amount: ${mapping.amount || "Not selected"}` : `Debit: ${mapping.debit || "Not selected"} / Credit: ${mapping.credit || "Not selected"}`} · Currency: {mapping.currency ?? mapping.fixed_currency ?? "Not selected"} · Format: {dateFormat || "Needs confirmation"}</p>
      <button className="text-button" disabled={busy || attempted} aria-expanded={showMapping} onClick={() => setShowMapping(!showMapping)}>{showMapping ? "Hide mapping" : "Review mapping"}</button>
      {(showMapping || needsAnswers) && <fieldset disabled={busy || attempted}>
        <legend className="sr-only">Column mapping</legend>
        {inspection.profiles.length > 0 && (showMapping || questions.includes("profile")) && <label>Suggested saved mappings<select aria-label="Suggested saved mappings" defaultValue="" onChange={event => {
          const profile = inspection.profiles.find(p => p.id === event.target.value);
          if (event.target.value === "custom") {setProfileConfirmed(true); setShowMapping(true);}
          if (profile) {edit(profile.mapping); setDateFormat(profile.mapping.date_format); setProfileConfirmed(true); setSignConfirmed(true);}
        }}><option value="">Review a compatible profile</option><option value="custom">Use my own mapping choices</option>{inspection.profiles.map(profile => <option key={profile.id} value={profile.id}>Suggested mapping: {profile.name}</option>)}</select></label>}
        <div className="mapping-fields">
          {showMapping && <>{selector("Transaction date", "transaction_date")}
          {selector("Description", "description")}
          <label>Amount mode<select aria-label="Amount mode" value={mapping.amount_mode} onChange={event => edit({amount_mode: event.target.value as ColumnMapping["amount_mode"], amount: null, debit: null, credit: null})}><option value="single">Single signed amount</option><option value="debit_credit">Debit + Credit</option></select></label>
          {mapping.amount_mode === "single" ? selector("Amount", "amount") : <>{selector("Debit", "debit")}{selector("Credit", "credit")}</>}
          </>}
          {(showMapping || questions.includes("currency")) && <>{selector("Currency column", "currency")}
          <label>Statement currency<select aria-label="Statement currency" value={mapping.fixed_currency ?? ""} onChange={event => edit({fixed_currency: (event.target.value || null) as ColumnMapping["fixed_currency"], currency: null})}><option value="">Use a currency column</option>{["AED","USD","EUR","GBP"].map(currency => <option key={currency}>{currency}</option>)}</select></label>
          </>}
          {(showMapping || questions.includes("date_format")) && <label>Date format<select aria-label="Date format" value={dateFormat} onChange={event => {setDateFormat(event.target.value); edit({date_format: event.target.value as ColumnMapping["date_format"]});}}><option value="">Select / confirm date format</option>{["YYYY-MM-DD","DD/MM/YYYY","MM/DD/YYYY","DD-MM-YYYY"].map(format => <option key={format}>{format}</option>)}</select></label>}
        </div>
        {questions.includes("sign_convention") && <label><input type="checkbox" checked={signConfirmed} onChange={event => setSignConfirmed(event.target.checked)} />Positive amounts are inflows; keep the source signs. If these are unsigned expenses, correct the source or use debit/credit columns.</label>}
        {!dateFormat && <p className="notice">Confirm the date format. For example, 03/04/2026 can mean 3 April or March 4.</p>}
        <p className="hint">Single amounts keep their signs. Debit and credit must be unsigned, with the unused column blank (including zero placeholders). Debits become negative; credits positive. No currency conversion or thousands separators.</p>
        <button className="primary" onClick={() => void preview()} disabled={!dateFormat || (questions.includes("sign_convention") && !signConfirmed) || (questions.includes("profile") && !profileConfirmed)}>Preview normalized rows</button>
      </fieldset>}
      <h2>Normalized preview</h2>
      <p className="hint">{inspection.samples.length} representative rows shown, including errors when present; source cells are truncated to 500 characters. Validation checks all {inspection.total_rows} rows.</p>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Mapping sample rows"><table><thead><tr><th>Row</th><th>Source values</th><th>Normalized LedgerX values</th><th>Validation</th></tr></thead><tbody>
        {inspection.samples.map(row => <tr key={row.source_row_number}><td>{row.source_row_number}</td><td>{row.source.map((value,index) => <div key={index}><strong>{inspection.headers[index] ?? "Extra column"}:</strong> {value || "(blank)"}</div>)}</td><td>{row.normalized ? <>{dateLabel(row.normalized.transaction_date)}<br/>{row.normalized.description ?? "—"}<br/>{row.normalized.amount && row.normalized.currency ? displayMoney(row.normalized.amount,row.normalized.currency) : "—"}</> : "Choose mapping and preview"}</td><td>{row.normalized ? row.normalized.errors.length ? row.normalized.errors.map(issue => <p key={issue.code} className="row-error">{issue.message}</p>) : "Valid" : "Not validated"}</td></tr>)}
      </tbody></table></div>
      {inspection.invalid_rows !== null && <p className={inspection.invalid_rows ? "notice error" : "notice success"}>{inspection.invalid_rows ? `${inspection.invalid_rows} invalid rows block this import. Correct the mapping or source file, then preview again.` : `All ${inspection.total_rows} rows are valid. Review the samples before continuing.`}</p>}
      {inspection.invalid_rows === 0 && <p className="hint">Confirm adds all {inspection.total_rows} transactions to your history. Imported facts cannot be edited or deleted. Avoid overlapping statements.</p>}
      {inspection.invalid_rows === 0 && <button className="primary" disabled={busy} onClick={() => void stage()}>{attempted ? "Retry same upload" : "Confirm import"}</button>}
      {attempted && !busy && <p className="hint">Your file and mapping are locked for a safe retry with the same upload key.</p>}
    </section>}
  </>;
}

function SaveMappingProfile({id}: {id: string}) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {await api.saveMappingProfile(id, name.trim()); setSaved(true);}
    catch (e) {setError(errorMessage(e));}
    finally {setBusy(false);}
  }
  return <section className="data-section"><h2>Save this mapping for future imports</h2>
    <p>Only column choices and format settings are saved. Future uploads still require review.</p>
    {saved ? <p role="status" className="notice success">Mapping saved as {name}.</p> : <form onSubmit={save}>
      <label htmlFor="profile-name">Profile name</label><input id="profile-name" value={name} onChange={event => setName(event.target.value)} maxLength={80} required disabled={busy} placeholder="My account CSV" />
      <button disabled={busy || !name.trim()}>{busy ? "Saving…" : "Save mapping"}</button>
      {error && <p role="alert" className="notice error">{error}</p>}
    </form>}
  </section>;
}

export function PreviewStatement({ id }: { id: string }) {
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [rows, setRows] = useState<RowPage | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const finalizeKey = useRef("");
  // A stable operation key is derived from this immutable import ID. No storage needed.
  useEffect(() => {
    let active = true;
    finalizeKey.current = id;
    api
      .preview(id)
      .then((value) => {
        if (active) {
          setPreview(value);
          setRows(value.rows);
        }
      })
      .catch((e) => {
        if (active) setError(errorMessage(e));
      });
    return () => {
      active = false;
    };
  }, [id, reload]);
  async function finalize() {
    setBusy(true);
    setError("");
    try {
      await api.finalize(id, finalizeKey.current);
      const value = await api.preview(id);
      setPreview(value);
      setRows(value.rows);
    } catch (e) {
      setError(errorMessage(e));
      try {
        const value = await api.preview(id);
        setPreview(value);
        setRows(value.rows);
      } catch {
        /* Keep the preview and same retry key after network failure. */
      }
    } finally {
      setBusy(false);
    }
  }
  async function page(after: number) {
    setBusy(true);
    setError("");
    try {
      setRows(await api.rows(id, after));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link href="/app/import" className="back">
        ← New upload
      </Link>
      {error && (
        <div className="notice error" role="alert">
          {error}
          <button
            disabled={busy}
            onClick={() => {
              setError("");
              setReload((n) => n + 1);
            }}
          >
            Refresh preview
          </button>
        </div>
      )}
      {!preview ? (
        !error && (
          <div className="loading" role="status">
            Loading statement preview…
          </div>
        )
      ) : (
        <>
          <div className="page-heading">
            <div>
              <p className="eyebrow">Statement review</p>
              <h1>
                {preview.status === "completed"
                  ? "Your history is ready."
                  : preview.status === "invalid"
                    ? "A few things to fix."
                    : preview.status === "expired"
                      ? "This preview expired."
                      : "Review before adding."}
              </h1>
              <p>
                {preview.status === "completed"
                  ? `${preview.accepted_rows} transactions added to your history.`
                  : "Check the results below. Nothing is added until you finalize."}
              </p>
            </div>
            <span className="status-label">{preview.status}</span>
          </div>
          <div className="preview-summary">
            <div>
              <span>Total rows</span>
              <strong>{preview.total_rows}</strong>
            </div>
            <div>
              <span>Valid rows</span>
              <strong>{preview.valid_rows}</strong>
            </div>
            <div>
              <span>Invalid rows</span>
              <strong>{preview.invalid_rows}</strong>
            </div>
            <div>
              <span>Currencies</span>
              <strong className="summary-text">
                {preview.currencies.join(" / ") || "None"}
              </strong>
            </div>
          </div>
          {preview.period_start && (
            <p className="hint">
              Valid-row date range: {dateLabel(preview.period_start)} to{" "}
              {dateLabel(preview.period_end)}. This is observed coverage, not a certified
              statement period.
            </p>
          )}
          {preview.status === "invalid" && (
            <p role="alert" className="notice error">
              The whole import is blocked because at least one row is invalid.
              Review the row-level reasons, fix your CSV, and upload it again.
              No transactions have been added.
            </p>
          )}
          {preview.status === "expired" && (
            <p className="notice">
              Previews expire after 24 hours.{" "}
              <Link href="/app/import">Upload your statement again</Link> to
              continue.
            </p>
          )}
          {preview.status === "completed" && (
            <div className="notice success" role="status">
              Import finalized.{" "}
              <Link className="button primary" href="/app/transactions">
                View transactions
              </Link>
            </div>
          )}
          {rows && rows.items.length > 0 && (
            <section className="data-section">
              <h2>
                {preview.status === "completed"
                  ? "Imported records"
                  : "Parsed records"}
              </h2>
              <div className="table-scroll" tabIndex={0} role="region" aria-label="Statement rows, scroll horizontally on small screens">
                <table>
                  <caption className="sr-only">
                    Parsed CSV records and validation results
                  </caption>
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Date / description</th>
                      <th className="amount">Amount</th>
                      <th>Validation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.items.map((row) => (
                      <tr key={row.source_row_number}>
                        <td>{row.source_row_number}</td>
                        <td>
                          {dateLabel(row.transaction_date)}
                          <span className="description">
                            {row.description ??
                              "Invalid row content is not retained"}
                          </span>
                        </td>
                        <td className="amount">
                          {row.amount && row.currency
                            ? displayMoney(row.amount, row.currency)
                            : "Unavailable"}
                        </td>
                        <td>
                          {row.errors.length
                            ? row.errors.map((issue, index) => (
                                <p className="row-error" key={index}>
                                  {issue.message}
                                </p>
                              ))
                            : "Valid"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="pagination">
                <p>Showing {rows.items.length} records</p>
                <div>
                  <button
                    disabled={busy || rows.items[0]?.source_row_number === 2}
                    onClick={() => void page(0)}
                  >
                    First rows
                  </button>
                  <button
                    disabled={busy || rows.next_after_row === null}
                    onClick={() =>
                      rows.next_after_row !== null &&
                      void page(rows.next_after_row)
                    }
                  >
                    {busy ? "Please wait…" : "Next rows"}
                  </button>
                </div>
              </div>
            </section>
          )}
          {preview.can_finalize && (
            <section className="finalize-panel">
              <div>
                <h2>Ready to add this statement?</h2>
                <p>
                  Finalize all {preview.valid_rows} transactions. Imported
                  financial facts cannot be edited or deleted through this app.
                </p>
                <p className="hint">
                  Avoid overlapping uploads: duplicate detection across
                  statements is not available. Preview expires{" "}
                  {new Date(preview.expires_at).toLocaleString()}.
                </p>
              </div>
              <button
                className="primary"
                disabled={busy}
                onClick={() => void finalize()}
              >
                {busy ? "Finalizing…" : "Finalize import"}
              </button>
            </section>
          )}
          {preview.status === "invalid" && (
            <Link className="button primary" href="/app/import">
              Upload corrected CSV
            </Link>
          )}
          {preview.can_save_mapping && <SaveMappingProfile key={id} id={id} />}
        </>
      )}
    </>
  );
}
