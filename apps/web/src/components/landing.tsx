import Link from "next/link";
import { ProductExample } from "./product-example";
import { IntelligenceExamples } from "./intelligence-examples";

export function Landing() {
  return (
    <div className="marketing">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="marketing-nav">
        <Link href="/" className="brand" aria-label="LedgerX home">
          Ledger<span>X</span>
        </Link>
        <nav aria-label="Public navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#the-bigger-picture">The bigger picture</a>
        </nav>
        <div className="nav-actions">
          <Link href="/login" className="sign-in">
            Sign in
          </Link>
          <Link href="/register" className="button primary">
            Create account <span aria-hidden="true">↗</span>
          </Link>
        </div>
      </header>
      <main id="main">
        <section className="marketing-hero">
          <div className="hero-copy">
            <p className="eyebrow">Personal financial intelligence</p>
            <h1>
              Your money.
              <br />
              <span>In perspective.</span>
            </h1>
            <p>
              Turn everyday transactions into understandable history. Build the
              foundation for a clearer picture of your financial life.
            </p>
            <div className="hero-actions">
              <Link className="button primary" href="/register">
                Create account <span aria-hidden="true">↗</span>
              </Link>
              <a className="text-link" href="#how-it-works">
                See how it works <span aria-hidden="true">↓</span>
              </a>
            </div>
          </div>
          <ProductExample />
        </section>
        <section className="understand-section" id="how-it-works">
          <div className="section-title">
            <h2>
              A transaction is a fact.
              <br />
              Understanding gives it context.
            </h2>
            <p>
              Start with your history. Keep the detail. Make it easier to see
              what happened.
            </p>
          </div>
          <div className="process-layout">
            <div className="process-start">
              <span className="process-label">Start here</span>
              <h3>
                Your history,
                <br />
                brought together.
              </h3>
              <p>
                Upload a statement in canonical CSV format. Review the
                validation results, then choose when to add it.
              </p>
              <span className="process-format">
                CSV upload → review → finalize
              </span>
            </div>
            <div className="process-steps">
              <article>
                <span aria-hidden="true">↳</span>
                <div>
                  <h3>Readable transactions</h3>
                  <p>
                    Consistent descriptions make activity easier to recognize.
                    The original financial facts stay intact.
                  </p>
                </div>
              </article>
              <article>
                <span aria-hidden="true">↳</span>
                <div>
                  <h3>Merchants with meaning</h3>
                  <p>
                    Recognized merchants and explainable categories put everyday
                    activity in context. You can correct the category.
                  </p>
                </div>
              </article>
              <article>
                <span aria-hidden="true">↳</span>
                <div>
                  <h3>History you can return to</h3>
                  <p>
                    Finalized transactions become part of your private
                    workspace, ready for your next review.
                  </p>
                </div>
              </article>
            </div>
          </div>
        </section>
        <section className="vision-section" id="the-bigger-picture">
          <div className="vision-heading">
            <p className="eyebrow">The direction ahead</p>
            <h2>Your history has more to tell you.</h2>
            <p>
              LedgerX is being built to learn from your transaction history: see
              what changed, understand what caused it, and find your normal.
            </p>
            <p className="vision-disclosure">
              Today: transaction history, merchant recognition and category
              corrections. Behavioral analysis is planned, not yet available.
            </p>
          </div>
          <IntelligenceExamples />
          <div className="history-horizon">
            <article>
              <span>One statement</span>
              <h3>Understand what happened.</h3>
              <p>Review your transactions, merchants and categories.</p>
              <strong>Available today</strong>
            </article>
            <article>
              <span>Several months</span>
              <h3>Find your normal.</h3>
              <p>
                The foundation for personal baselines and recurring commitments.
              </p>
              <strong>Planned intelligence</strong>
            </article>
            <article>
              <span>Longer history</span>
              <h3>See what’s changing.</h3>
              <p>
                The foundation for understanding patterns, shifts and unusual
                activity.
              </p>
              <strong>Planned intelligence</strong>
            </article>
          </div>
        </section>
        <section className="trust-section" id="your-data">
          <div>
            <h2>
              Personal history.
              <br />A private workspace.
            </h2>
            <p>
              Your financial data deserves clear boundaries, and clear
              explanations of what is stored.
            </p>
          </div>
          <dl>
            <div>
              <dt>Access belongs to you.</dt>
              <dd>
                Authenticated access and owner-scoped records keep each user’s
                financial history separate.
              </dd>
            </div>
            <div>
              <dt>The history stays. The raw file doesn’t.</dt>
              <dd>
                Uploaded CSV contents are transient. Finalized, normalized
                transactions are stored in your private workspace.
              </dd>
            </div>
            <div>
              <dt>You stay in control of the meaning.</dt>
              <dd>
                Review before finalizing. Correct categories while preserving
                the original imported facts.
              </dd>
            </div>
          </dl>
        </section>
        <section className="closing-section">
          <h2>
            Start with your history.
            <br />
            <span>See it more clearly.</span>
          </h2>
          <Link className="button primary" href="/register">
            Create account <span aria-hidden="true">↗</span>
          </Link>
        </section>
      </main>
      <footer className="marketing-footer">
        <Link href="/" className="brand">
          Ledger<span>X</span>
        </Link>
        <p>Financial history. A clearer perspective.</p>
        <Link href="/login">Sign in</Link>
      </footer>
    </div>
  );
}
