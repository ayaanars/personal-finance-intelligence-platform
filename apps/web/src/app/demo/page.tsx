import Link from "next/link";

export default function Demo() {
  return <main className="auth-page"><section className="auth-panel"><div className="auth-form">
    <Link className="brand" href="/">Ledger<span>X</span></Link>
    <p className="eyebrow">Fictional demo history</p>
    <h1>Explore LedgerX safely</h1>
    <p>Use a private account and eight months of synthetic AED transactions. No bank connection or real statement is needed.</p>
    <ol>
      <li><Link href="/register">Create your private account</Link> or <Link href="/login">sign in</Link>.</li>
      <li><a href="/demo/fictional-history.csv" download>Download the fictional statement</a>.</li>
      <li><Link href="/app/import">Import Statement</Link>: upload the CSV, review the recognized preview, then confirm the import.</li>
    </ol>
    <p>Open Overview, Insights, Trends, Unusual Activity, Relationships, Forecast, Recurring, Behaviour and Transactions. Choose August 2026 for the latest demo period.</p>
    <p className="notice">All history is fictional. Results describe this sample, not your finances. Forecast availability follows the normal historical-period rules. Use a fresh account to keep demo history separate from any personal imports.</p>
  </div></section></main>;
}
