import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IntelligenceExamples } from "@/components/intelligence-examples";
import { LineChart } from "@/features/intelligence-charts";

describe("polished product previews", () => {
  it("shows shipped capabilities with synthetic disclosure and excludes unsupported signals", async () => {
    render(<IntelligenceExamples />);
    expect(screen.queryByRole("button", {name:"New location"})).not.toBeInTheDocument();
    expect(screen.queryByRole("button", {name:"Unusual time"})).not.toBeInTheDocument();
    expect(screen.getByRole("region", {name:"Planning and relationships examples"})).toBeInTheDocument();
    expect(screen.getByRole("img", {name:"Synthetic spending: AED 3,200 observed, approximately AED 3,840 projected"})).toBeInTheDocument();
    expect(screen.queryByText("A target, with perspective.")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", {name:"Annual estimate"}));
    expect(screen.getByText("AED 3,864")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", {name:"First-time merchant"}));
    expect(screen.getByText("An unfamiliar merchant")).toBeInTheDocument();
  });
  it("highlights the latest observation by default and supports keyboard exploration", async () => {
    render(<LineChart currency="AED" label="Spending" points={[{month:"2026-08",value:"20.0000"},{month:"2026-09",value:"30.0000"}]} />);
    expect(screen.getByRole("button", {name:"September 2026: 30.00 AED"})).toHaveAttribute("aria-pressed","true");
    await userEvent.tab();
    expect(screen.getByRole("button", {name:"August 2026: 20.00 AED"})).toHaveAttribute("aria-pressed","true");
  });
});

it("uses semantic activity labels without inventing a merchant", async () => {
  const { ActivitySummary } = await import("@/components/transaction-activity");
  render(<ActivitySummary activity={{merchant:null,display_name:"Rent",normalized_description:"RENT PAYMENT",raw_description:"RENT PAYMENT",amount:"-1000.0000",currency:"AED",category:"Housing",transaction_date:"2026-09-01"}} />);
  expect(screen.getByText("Rent")).toBeVisible();
  expect(screen.getByText("Housing")).toBeVisible();
  expect(screen.queryByText("Unknown merchant")).not.toBeInTheDocument();
});
it("keeps chart selection valid when a period has fewer observations", async () => {
  const view=render(<LineChart currency="AED" label="Spending" points={[{month:"2026-08",value:"20.0000"},{month:"2026-09",value:"30.0000"}]} />);
  await userEvent.click(screen.getByRole("button",{name:"September 2026: 30.00 AED"}));
  view.rerender(<LineChart currency="AED" label="Spending" points={[{month:"2026-08",value:"20.0000"}]} />);
  expect(screen.getByRole("button",{name:"August 2026: 20.00 AED"})).toHaveAttribute("aria-pressed","true");
});

it("shows observed recurring months before expanding supporting evidence", async () => {
  const { RecurringCommitments } = await import("@/features/overview-history");
  const { data } = await import("./intelligence-fixture");
  const currency=structuredClone(data.currencies[0]);
  currency.recurring={...currency.recurring,state:"likely_recurring",payments:[{merchant:"Netflix",typical_amount:"49.0000",annual_estimate:"588.0000",frequency:"monthly",newly_qualified:false,reason:"Three observed payments.",share_percent:"100.00",evidence:[7,8,9].map(month=>({identifier:String(month),day:`2026-0${month}-07`,amount:"49.0000"}))}]};
  render(<RecurringCommitments data={currency}/>);
  expect(screen.getByLabelText("Netflix observed charge months")).toHaveTextContent("July 2026");
  expect(screen.getByLabelText("Netflix observed charge months")).toHaveTextContent("September 2026");
  expect(screen.getByText("Why this looks recurring").closest("details")).not.toHaveAttribute("open");
});
