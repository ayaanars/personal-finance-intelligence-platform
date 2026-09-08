"use client";
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
} from "@/lib/api";

export function UploadStatement() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const key = useRef("");
  const [attempted, setAttempted] = useState(false);
  useEffect(() => {
    if (!attempted || !file) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [attempted, file]);
  function choose(candidate?: File) {
    if (busy || attempted) return;
    setError("");
    if (!candidate) return;
    if (
      !candidate.name.toLowerCase().endsWith(".csv") ||
      candidate.size > 5 * 1024 * 1024 ||
      candidate.size === 0
    ) {
      setFile(null);
      setError("Choose a non-empty .csv file no larger than 5 MiB.");
      return;
    }
    key.current = crypto.randomUUID();
    setFile(candidate);
  }
  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    setError("");
    setAttempted(true);
    try {
      const preview = await api.upload(file, key.current);
      setFile(null);
      router.push(`/app/import/${preview.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
      // A rejected format/size/auth boundary created no batch; permit a corrected file.
      // Uncertain responses retain both bytes and key for a safe retry.
      if (
        e instanceof ApiError &&
        [400, 401, 403, 413, 415, 422].includes(e.status)
      )
        setAttempted(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Bring your history together</p>
          <h1>
            A statement.
            <br />A starting point.
          </h1>
          <p>
            Upload a canonical CSV, review every result, then choose to add it
            to your history.
          </p>
        </div>
      </div>
      <div className="import-grid">
        <section className="data-section">
          <h2>Choose your statement</h2>
          <form onSubmit={upload}>
            <div
              className="dropzone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                choose(e.dataTransfer.files[0]);
              }}
            >
              <span className="empty-mark" aria-hidden="true">
                ↗
              </span>
              <label htmlFor="csv">
                {file ? file.name : "Drop a CSV here, or choose a file"}
              </label>
              <p className="hint">UTF-8 CSV · Up to 5 MiB · 25,000 rows</p>
              <input
                id="csv"
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => choose(e.target.files?.[0])}
                disabled={busy || attempted}
              />
            </div>
            {error && (
              <p className="notice error" role="alert">
                {error}
              </p>
            )}
            {busy && (
              <p role="status" className="notice">
                Uploading and validating your statement. This may take a moment…
              </p>
            )}
            <button className="primary full" disabled={!file || busy}>
              {busy
                ? "Preparing preview…"
                : attempted
                  ? "Retry same upload"
                  : "Review statement"}
            </button>
            {attempted && !busy && (
              <p className="hint">
                Retry keeps the same upload key to avoid creating another
                import. To select a different file, leave this page and start a
                new upload.
              </p>
            )}
          </form>
          <p className="hint">
            Uploading does not add transactions to your history. Finalization is
            a separate step.
          </p>
        </section>
        <aside className="format-guide">
          <h2>A simple, exact format.</h2>
          <p>
            Use these four column names. Bank exports may need to be converted
            to this format first.
          </p>
          <code className="csv-header">
            transaction_date,description,amount,currency
          </code>
          <dl>
            <dt>transaction_date</dt>
            <dd>Calendar date, such as 2026-08-01.</dd>
            <dt>description</dt>
            <dd>Original transaction text, up to 500 characters.</dd>
            <dt>amount</dt>
            <dd>
              Positive for inflows, negative for outflows. Up to four decimal
              places; no thousands separators.
            </dd>
            <dt>currency</dt>
            <dd>AED, USD, EUR or GBP. Currencies stay separate.</dd>
          </dl>
          <p className="hint">
            Raw CSV contents are not retained. Independent uploads can contain
            duplicates, so avoid importing overlapping statements.
          </p>
        </aside>
      </div>
    </>
  );
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
              Valid-row date range: {preview.period_start} to{" "}
              {preview.period_end}. This is observed coverage, not a certified
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
                          {row.transaction_date ?? "Unavailable"}
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
        </>
      )}
    </>
  );
}
