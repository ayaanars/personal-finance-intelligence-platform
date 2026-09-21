import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { Goals } from "@/features/goals";
import { planSchema } from "@/lib/goals";
const plan = planSchema.parse({ month: "2026-09", available_months: ["2026-09", "2026-08"], goals: [{
            kind: "spending", currency: "AED", target: "7000.0000", active: true, actual: "3200.0000", projected: "6400.0000", status: "On track", pace_target: "3500.0000"
        }], currencies: [{ currency: "AED", state: "estimate", quality: "Early estimate", elapsed_days: 15, days_in_month: 30, history_months: 0, observed_span_days: 15, last_activity: "2026-09-15", actual_spending: "3200.0000", actual_outflow: "3200.0000", actual_net_cash_flow: "1800.0000", projected_spending: "6400.0000", projected_outflow: "6400.0000", projected_net_cash_flow: "3600.0000", remaining_recurring: "100.0000", commitments: [{ merchant: "Netflix", amount: "100.0000", state: "remaining", expected_day: "2026-09-20" }], explanation: "Limited history; using current pace only.", insight: null }] });
it("renders forecast, goal progress, quality and readable recurring evidence", async () => {
    vi.spyOn(api, "plan").mockResolvedValue(plan);
    render(<Goals />);
    expect(await screen.findByRole("heading", { name: "7,000.00 AED" })).toBeVisible();
    expect(screen.getByText("On track")).toBeVisible();
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", expect.stringContaining("projected ≈ 6,400 AED"));
    expect(screen.getByText(/Early estimate/)).toBeVisible();
    expect(screen.getByText(/Limited-history forecast/)).toBeVisible();
    expect(screen.getByText(/20 September 2026/)).toBeVisible();
    expect(screen.queryByText("2026-09-20")).not.toBeInTheDocument();
});
it("creates a net cash flow goal and edits active state", async () => {
    vi.spyOn(api, "plan").mockResolvedValue(plan);
    const save = vi.spyOn(api, "saveGoal").mockResolvedValue(undefined);
    render(<Goals />);
    await screen.findByText("On track");
    await userEvent.selectOptions(screen.getByLabelText("Goal"), "net_cash_flow");
    await userEvent.type(screen.getByRole("textbox", { name: "Target amount" }), "2000");
    await userEvent.click(screen.getByRole("button", { name: "Save goal" }));
    await waitFor(() => expect(save).toHaveBeenCalledWith({ month: "2026-09", currency: "AED", kind: "net_cash_flow", target: "2000", active: true }));
    await userEvent.click(screen.getByText("Edit goal"));
    const inputs = screen.getAllByRole("checkbox", { name: "Active" });
    await userEvent.click(inputs[0]);
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(save).toHaveBeenLastCalledWith(expect.objectContaining({ kind: "spending", active: false })));
});
it("keeps currencies separate and selected month explicit", async () => {
    const fetcher = vi.spyOn(api, "plan").mockResolvedValue(plan);
    render(<Goals />);
    await screen.findByText("On track");
    await userEvent.click(screen.getByRole("button", { name: "USD" }));
    expect(screen.queryByText("On track")).not.toBeInTheDocument();
    expect(screen.getByText("Set your first target")).toBeVisible();
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Month" }), "2026-08");
    await waitFor(() => expect(fetcher).toHaveBeenLastCalledWith("2026-08"));
});
it("shows a compact summary and an actionable error", async () => {
    const fetcher = vi.spyOn(api, "plan").mockResolvedValue(plan);
    const view = render(<Goals compact selectedCurrency="AED"/>);
    await screen.findByText(/7,000.00 AED target/);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/app/goals");
    view.unmount();
    fetcher.mockRejectedValue(new Error("unavailable"));
    render(<Goals />);
    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeVisible();
});

it("removes only the selected monthly goal after its inline confirmation", async () => {
    vi.spyOn(api, "plan").mockResolvedValue(plan);
    const remove = vi.spyOn(api, "removeGoal").mockResolvedValue(undefined);
    render(<Goals/>);
    await screen.findByText("On track");
    await userEvent.click(screen.getByText("Edit goal"));
    await userEvent.click(screen.getByText("Remove goal"));
    expect(remove).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", {name:"Confirm removal"}));
    await waitFor(()=>expect(remove).toHaveBeenCalledWith({month:"2026-09",currency:"AED",kind:"spending"}));
    expect(await screen.findByText("Goal removed.")).toBeVisible();
});
