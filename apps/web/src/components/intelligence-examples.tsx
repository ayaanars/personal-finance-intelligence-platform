"use client";

import { useState, type CSSProperties } from "react";

// Illustrative public concepts, not calculations or results from a user's account.
// Display amounts and chart geometry are separate, predefined example values.
const months = [
  {
    name: "Apr",
    amount: "460",
    height: "51%",
    context: "Within the illustrated typical range.",
  },
  {
    name: "May",
    amount: "490",
    height: "54%",
    context: "Within the illustrated typical range.",
  },
  {
    name: "Jun",
    amount: "510",
    height: "57%",
    context: "Near the upper end of the illustrated range.",
  },
  {
    name: "Jul",
    amount: "470",
    height: "52%",
    context: "Within the illustrated typical range.",
  },
  {
    name: "Aug",
    amount: "500",
    height: "56%",
    context: "Within the illustrated typical range.",
  },
  {
    name: "Sep",
    amount: "810",
    height: "90%",
    context: "Above the illustrated range. A change worth understanding.",
  },
];
const commitments = [
  { name: "Netflix", category: "Entertainment", monthly: "49", annual: "588" },
  { name: "Spotify", category: "Entertainment", monthly: "23", annual: "276" },
  { name: "Gym", category: "Health", monthly: "250", annual: "3,000" },
];
const unusual = [
  {
    label: "Large purchase",
    merchant: "Electronics purchase",
    amount: "2,450.00",
    detail: "Higher than the other purchases in this example history.",
    context:
      "A larger amount can be intentional. Context helps you decide what deserves a second look.",
  },
  {
    label: "First-time merchant",
    merchant: "An unfamiliar merchant",
    amount: "320.00",
    detail: "The first appearance of this merchant in the example history.",
    context:
      "A new shop or service may be perfectly ordinary. The goal is to make unfamiliar activity easier to review.",
  },
];

export function IntelligenceExamples() {
  const [month, setMonth] = useState(5);
  const [annual, setAnnual] = useState(false);
  const [signal, setSignal] = useState(0);
  const selected = months[month];
  const activity = unusual[signal];
  return (
    <div className="intelligence-examples">
      <section
        className="spending-demo concept-surface"
        aria-labelledby="spending-title"
      >
        <div className="concept-caption">
          <span>Spending & personal baseline</span>
          <span>Synthetic example</span>
        </div>
        <div className="concept-body">
          <h3 id="spending-title">
            See what changed.
            <br />
            Find your normal.
          </h3>
          <p>One month makes more sense beside the months before it.</p>
          <div className="spending-readout" aria-live="polite">
            <div>
              <span>Dining · {selected.name}</span>
              <strong>AED {selected.amount}</strong>
            </div>
            <div className="baseline-readout">
              <span>Illustrative typical range</span>
              <strong>
                AED 420–520<span> / month</span>
              </strong>
            </div>
          </div>
          <figure className="spending-chart">
            <figcaption className="sr-only">
              Illustrative monthly dining spend in AED. Select a month to
              explore.
            </figcaption>
            <div className="chart-baseline" aria-hidden="true">
              <span>Typical range</span>
            </div>
            <div className="chart-columns">
              {months.map((item, index) => (
                <button
                  key={item.name}
                  className="chart-month"
                  aria-label={`${item.name}: AED ${item.amount} dining spend`}
                  aria-pressed={index === month}
                  onClick={() => setMonth(index)}
                  style={{ "--bar-height": item.height } as CSSProperties}
                >
                  <span className="chart-value">{item.amount}</span>
                  <span className="chart-bar" aria-hidden="true" />
                  <span className="chart-month-name">{item.name}</span>
                </button>
              ))}
            </div>
          </figure>
          <p className="chart-context" aria-live="polite" key={month}>
            {selected.context}
          </p>
          <div className="demo-takeaway">
            <strong>Then ask why.</strong>
            <span>
              Follow the evidence from a change to the transactions behind it.
            </span>
          </div>
        </div>
      </section>
      <section
        className="recurring-demo concept-surface"
        aria-labelledby="recurring-title"
      >
        <div className="concept-caption">
          <span>Recurring commitments</span>
          <span>Synthetic example</span>
        </div>
        <div className="concept-body">
          <h3 id="recurring-title">
            The small amounts
            <br />
            that keep coming back.
          </h3>
          <p>
            Bring repeat commitments into one view, then see the longer-term
            picture.
          </p>
          <div
            className="period-selector"
            role="group"
            aria-label="Illustrative commitment period"
          >
            <button aria-pressed={!annual} onClick={() => setAnnual(false)}>
              Monthly
            </button>
            <button aria-pressed={annual} onClick={() => setAnnual(true)}>
              Annual estimate
            </button>
          </div>
          <div className="preview-cadence" aria-label="Synthetic monthly payment evidence"><span>Jul ●</span><span>Aug ●</span><span>Sep ●</span></div>
          <div className="commitment-list" aria-live="polite">
            {commitments.map((item) => (
              <div className="commitment" key={item.name}>
                <div>
                  <strong>{item.name}</strong>
                  <span>{item.category}</span>
                </div>
                <strong className="commitment-amount">
                  AED {annual ? item.annual : item.monthly}
                </strong>
              </div>
            ))}
          </div>
          <div className="commitment-total" aria-live="polite">
            <span>
              {annual
                ? "Estimated annual commitment"
                : "Combined monthly commitment"}
            </span>
            <strong>AED {annual ? "3,864" : "322"}</strong>
          </div>
          <p className="concept-note">
            Example amounts, not current provider prices. Annual illustration
            assumes 12 unchanged monthly payments.
          </p>
        </div>
      </section>
      <section
        className="unusual-demo concept-surface"
        aria-labelledby="unusual-title"
      >
        <div className="concept-caption">
          <span>Unusual activity</span>
          <span>Synthetic example</span>
        </div>
        <div className="unusual-content">
          <div className="unusual-intro">
            <h3 id="unusual-title">
              A reason to look closer.
              <br />
              Room for an explanation.
            </h3>
            <p>
              Notice what differs from your history, with context instead of
              certainty.
            </p>
            <div
              className="signal-selector"
              role="group"
              aria-label="Explore unusual activity concepts"
            >
              {unusual.map((item, index) => (
                <button
                  key={item.label}
                  aria-pressed={index === signal}
                  onClick={() => setSignal(index)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <div className="unusual-example" aria-live="polite">
            <div className="signal-content" key={signal}>
              <span className="signal-label">Example for review</span>
              <div className="signal-transaction">
                <h4>{activity.merchant}</h4>
                <strong>AED {activity.amount}</strong>
              </div>
              <p className="signal-reason">{activity.detail}</p>
              <p>{activity.context}</p>
            </div>
          </div>
        </div>
        <p className="unusual-footnote">
          Advisory signals based on imported history, not proof of fraud.
          Examples use synthetic data; personal results require sufficient history.
        </p>
      </section>
      <section className="planning-preview" aria-label="Planning and relationships examples">
        <article><span>Synthetic planning example · AED</span><h3>Your month, in perspective.</h3><strong>3,200 observed · ≈ 3,840 projected</strong><p>Spending so far and a conditional month-end outlook. Forecasts depend on observed coverage and the pace of activity.</p><div className="goal-track" role="img" aria-label="Synthetic spending: AED 3,200 observed, approximately AED 3,840 projected"><span style={{width:"83.33%"}} /></div><p>Day 25 of 30 · conditional estimate AED 3,840. Bar: observed spending as a share of that projection.</p></article>
        <article><span>Synthetic relationship example</span><h3>Two patterns, side by side.</h3><strong>Dining ↔ transport</strong><p>Explore how spending categories move together across observed months. Association does not establish a cause.</p><div className="preview-cadence"><span>Jul · AED 470 / 220</span><span>Aug · 500 / 240</span><span>Sep · 810 / 380</span></div></article>
      </section>
    </div>
  );
}
