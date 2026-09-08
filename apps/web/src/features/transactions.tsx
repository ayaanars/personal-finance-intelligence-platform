"use client";
import Link from "next/link";
import { ActivitySummary } from "@/components/transaction-activity";
import { useEffect, useState } from "react";
import {
  api,
  categories,
  displayMoney,
  errorMessage,
  type Category,
  type Transaction,
} from "@/lib/api";

export function TransactionHistory() {
  const [items, setItems] = useState<Transaction[]>([]);
  const [cursor, setCursor] = useState<string>();
  const [next, setNext] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    api
      .transactions(cursor)
      .then((result) => {
        if (active) {
          setItems(result.items);
          setNext(result.page.next_cursor);
        }
      })
      .catch((e) => {
        if (active) setError(errorMessage(e));
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [cursor, reload]);
  function load(value?: string) {
    setBusy(true);
    setError("");
    setItems([]);
    setCursor(value);
    setReload((n) => n + 1);
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Your financial history</p>
          <h1>
            Every transaction,
            <br className="mobile-hide" /> a little clearer.
          </h1>
          <p>Real activity from the statements you’ve finalized.</p>
        </div>
        <Link className="button primary" href="/app/import">
          Import statement <span aria-hidden="true">↗</span>
        </Link>
      </div>
      <section className="data-section" aria-labelledby="history-title">
        <div className="section-heading">
          <h2 id="history-title">Transaction history</h2>
          <button
            className="text-button"
            disabled={busy}
            onClick={() => load()}
          >
            Refresh history
          </button>
        </div>
        {busy ? (
          <div className="loading" role="status">
            Loading your transactions…
          </div>
        ) : error ? (
          <div className="empty">
            <p role="alert">{error}</p>
            <button onClick={() => load(cursor)}>Retry</button>
          </div>
        ) : items.length === 0 ? (
          <div className="empty">
            <span className="empty-mark" aria-hidden="true">
              ↗
            </span>
            <h2>
              {cursor ? "You’ve reached the end." : "Your story starts here."}
            </h2>
            <p>
              {cursor
                ? "Refresh history to include newly imported transactions."
                : "Import your first bank statement to see your transactions, merchants and categories in one place."}
            </p>
            {cursor ? (
              <button onClick={() => load()}>Back to first page</button>
            ) : (
              <Link className="button primary" href="/app/import">
                Import your first statement
              </Link>
            )}
          </div>
        ) : (
          <>
            <div className="table-scroll" tabIndex={0} role="region" aria-label="Transactions, scroll horizontally on small screens">
              <table>
                <caption className="sr-only">
                  Finalized transactions, in stable record order
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Transaction / merchant</th>
                    <th scope="col">Date</th>
                    <th scope="col">Category</th>
                    <th scope="col" className="amount">
                      Amount
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <Link
                          className="transaction-link"
                          href={`/app/transactions/${item.id}`}
                        >
                          {item.merchant ?? item.normalized_description}
                        </Link>
                        <span className="description">
                          {item.raw_description}
                        </span>
                      </td>
                      <td className="nowrap">{item.transaction_date}</td>
                      <td>
                        <span className="category">{item.category}</span>
                        {item.categorization_source === "manual" && (
                          <span className="description">Your correction</span>
                        )}
                      </td>
                      <td className="amount">
                        <strong>
                          {displayMoney(item.amount, item.currency)}
                        </strong>
                        <span className="description">
                          {item.amount.startsWith("-") ? "Outflow" : "Inflow"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <p>
                {items.length} records on this page · Stable record order, not
                date order
              </p>
              <div>
                {cursor && <button onClick={() => load()}>First page</button>}
                <button disabled={!next} onClick={() => next && load(next)}>
                  Next page <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </>
  );
}

export function TransactionDetail({ id }: { id: string }) {
  const [item, setItem] = useState<Transaction | null>(null);
  const [selection, setSelection] = useState<Category | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    api
      .transaction(id)
      .then((value) => {
        if (active) {
          setItem(value);
          setSelection(
            value.categorization_source === "manual" ? value.category : "",
          );
        }
      })
      .catch((e) => {
        if (active) setError(errorMessage(e));
      });
    return () => {
      active = false;
    };
  }, [id, reload]);
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!item) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await api.category(item, selection || null);
      setItem(updated);
      setNotice("Category saved. Your original transaction is unchanged.");
    } catch (e) {
      setError(errorMessage(e));
      // An uncertain PATCH must be read back, never blindly replayed.
      try {
        const latest = await api.transaction(id);
        setItem(latest);
        setSelection(
          latest.categorization_source === "manual" ? latest.category : "",
        );
        setNotice(
          "Latest details loaded. Review the category before saving again.",
        );
      } catch {
        setItem(null);
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link className="back" href="/app/transactions">
        ← Transaction history
      </Link>
      {error && (
        <div className="notice error" role="alert">
          {error}
          {!item && (
            <button
              onClick={() => {
                setError("");
                setReload((n) => n + 1);
              }}
            >
              Reload details
            </button>
          )}
        </div>
      )}
      {!item ? (
        !error && (
          <div className="loading" role="status">
            Loading transaction…
          </div>
        )
      ) : (
        <>
          <div className="page-heading">
            <div>
              <p className="eyebrow">Transaction detail</p>
              <h1 className="detail-title">
                {item.merchant ?? item.normalized_description}
              </h1>
              <p>
                {item.transaction_date} ·{" "}
                {item.amount.startsWith("-") ? "Outflow" : "Inflow"}
              </p>
            </div>
            <div className="detail-activity">
              <ActivitySummary activity={item} />
            </div>
          </div>
          <div className="detail-grid">
            <section className="data-section">
              <h2>Original activity</h2>
              <dl>
                <dt>Imported description</dt>
                <dd className="preserve">{item.raw_description}</dd>
                <dt>Normalized description</dt>
                <dd>{item.normalized_description}</dd>
                <dt>Merchant</dt>
                <dd>{item.merchant ?? "Not identified"}</dd>
              </dl>
              <p className="hint">
                Imported amounts, dates and descriptions are preserved.
              </p>
            </section>
            <section className="data-section">
              <h2>Make the category yours</h2>
              <p>{item.categorization_reason}</p>
              <form onSubmit={save}>
                <label htmlFor="category">Category</label>
                <select
                  id="category"
                  value={selection}
                  onChange={(e) =>
                    setSelection(e.target.value as Category | "")
                  }
                  disabled={busy}
                >
                  <option value="">
                    Use automatic category ({item.automatic_category})
                  </option>
                  {categories.map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
                <p className="hint">
                  Your correction takes priority. Choose automatic to remove it.
                </p>
                <button className="primary" disabled={busy}>
                  {busy ? "Saving category…" : "Save category"}
                </button>
              </form>
              {notice && (
                <p className="notice" role="status">
                  {notice}
                </p>
              )}
              <details>
                <summary>Why this automatic category?</summary>
                <p>{item.automatic_reason}</p>
                <p className="hint">
                  Automatic category: {item.automatic_category}
                </p>
                {!item.enrichment_persisted && (
                  <p className="hint">
                    Calculated using current rules for an earlier import.
                  </p>
                )}
              </details>
            </section>
          </div>
        </>
      )}
    </>
  );
}
