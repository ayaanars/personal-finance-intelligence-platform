import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { dateLabel, monthLabel, readableDates } from "@/lib/dates";
import { UnusualActivity } from "@/features/unusual";
import { unusualSchema } from "@/lib/unusual";
it("formats calendar dates without timezone shifts, including leap and invalid dates", () => {
    expect(monthLabel("2026-08")).toBe("August 2026");
    expect(dateLabel("2026-08-07")).toBe("7 August 2026");
    expect(dateLabel("2024-02-29")).toBe("29 February 2024");
    expect(dateLabel("2026-02-29")).toBe("Unavailable date");
    expect(dateLabel(null)).toBe("Unavailable date");
    expect(readableDates("Compared with 2026-08 on 2026-09-01.")).toBe("Compared with August 2026 on 1 September 2026.");
});
const data = unusualSchema.parse({ month: "2026-09", available_months: ["2026-09"], methodology_version: "unusual-v1", coverage_note: "Imported history only.", currencies: [{ currency: "AED", state: "available", prior_months: ["2026-06", "2026-07", "2026-08"], historical_purchases: 30, ml_state: "insufficient_history", total: 1, items: [{ identifier: "purchase", subject: "Synthetic shop", day: "2026-09-07", severity: "High", ml_supported: false, transaction_ids: ["00000000-0000-4000-8000-000000000001"], evidence: [{ code: "large_purchase", explanation: "Above the personal purchase range.", current: "100.0000", reference: "10.0000", unit: "money", ratio: "10.00", reference_scale: "10.00" }] }] }] });
it("renders ranked evidence, readable dates, safe links and model status", async () => {
    vi.spyOn(api, "unusual").mockResolvedValue(data);
    render(<UnusualActivity />);
    await screen.findByRole("heading", { name: "Synthetic shop" });
    expect(screen.getByText("7 September 2026")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("10.00× reference")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Supporting history"));
    expect(screen.getByRole("link", { name: "View transaction 1 ↗" })).toHaveAttribute("href", "/app/transactions/00000000-0000-4000-8000-000000000001");
    expect(screen.queryByText(/2026-0[6789]/)).not.toBeInTheDocument();
});
it("keeps Overview compact and shows a recoverable API error", async () => {
    const fetcher = vi.spyOn(api, "unusual").mockResolvedValue(data);
    const view = render(<UnusualActivity compact selectedMonth="2026-09" selectedCurrency="AED"/>);
    await screen.findByText("1 unusual change · AED");
    expect(screen.queryByText("Synthetic shop")).not.toBeInTheDocument();
    view.unmount();
    fetcher.mockRejectedValue(new Error("Unavailable"));
    render(<UnusualActivity />);
    await screen.findByRole("alert");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
});
