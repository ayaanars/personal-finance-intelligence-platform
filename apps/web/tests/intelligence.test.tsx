import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
import { IntelligencePage } from "@/features/overview";
import { IntelligencePeriodProvider } from "@/features/intelligence-period";
import { LineChart, chartGeometry } from "@/features/intelligence-charts";
import { Shell } from "@/components/shell";
import { data } from "./intelligence-fixture";
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }), usePathname: () => "/app/trends" }));
it("exposes all private destinations, current page and expandable mobile navigation", async () => {
    render(<Shell><p>Page content</p></Shell>);
    for (const name of ['Overview', 'Insights', 'Trends', 'Recurring', 'Behaviour', 'Transactions', 'Import statement'])
        expect(screen.getByRole('link', { name })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Trends' })).toHaveAttribute('aria-current', 'page');
    const menu = screen.getByRole('button', { name: /Explore/ });
    expect(menu).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(menu);
    expect(menu).toHaveAttribute('aria-expanded', 'true');
    await userEvent.click(screen.getByRole('link', { name: 'Insights' }));
    expect(menu).toHaveAttribute('aria-expanded', 'false');
});
it("keeps selected month and currency across intelligence destinations", async () => {
    const result = { ...data, currencies: [data.currencies[0], { ...data.currencies[0], currency: 'USD' as const }] };
    const fetcher = vi.spyOn(api, 'intelligence').mockResolvedValue(result);
    const view = render(<IntelligencePeriodProvider><IntelligencePage page="overview"/></IntelligencePeriodProvider>);
    await screen.findByText('1,525.00 AED');
    await userEvent.click(screen.getByRole('button', { name: 'USD' }));
    await userEvent.selectOptions(screen.getByLabelText('Month'), '2026-08');
    await screen.findByText('1,525.00 USD');
    view.rerender(<IntelligencePeriodProvider><IntelligencePage key="trends" page="trends"/></IntelligencePeriodProvider>);
    await screen.findByRole('heading', { name: 'Your recent trends' });
    expect(fetcher).toHaveBeenLastCalledWith('2026-08');
    expect(screen.getByRole('button', { name: 'USD' })).toHaveAttribute('aria-pressed', 'true');
});
it("explores signed net cash flow, bounded historical categories and merchant gaps", async () => {
    const fetcher = vi.spyOn(api, 'intelligence').mockImplementation(async (month) => ({ ...data, month: month ?? data.month }));
    render(<IntelligencePage page="trends"/>);
    await screen.findByRole('heading', { name: 'Your recent trends' });
    await userEvent.click(screen.getByRole('button', { name: 'Net cash flow' }));
    expect(screen.getByRole('button', { name: 'September 2026: 1,525.00 AED' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Category' }));
    expect(await screen.findByLabelText('Category', { selector: 'select' })).toHaveValue('Groceries');
    expect(fetcher).toHaveBeenCalledWith('2026-03');
    expect(fetcher).toHaveBeenCalledTimes(7);
    await userEvent.click(screen.getByRole('button', { name: 'Merchant' }));
    expect(await screen.findByText(/top five spending merchants/)).toBeInTheDocument();
    expect(screen.getByText('No observations for this selection.')).toBeInTheDocument();
});
it("reports historical fetch failures and retries instead of plotting partial totals", async () => {
    vi.spyOn(api, 'intelligence').mockImplementation(async (month) => { if (month === '2026-03')
        throw new ApiError(0, 'NETWORK_ERROR'); return { ...data, month: month ?? data.month }; });
    render(<IntelligencePage page="trends"/>);
    await screen.findByRole('heading', { name: 'Your recent trends' });
    await userEvent.click(screen.getByRole('button', { name: 'Recurring' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry historical trends' })).toBeInTheDocument();
    expect(screen.queryByText('Estimated monthly recurring pattern')).not.toBeInTheDocument();
});
it("keeps dedicated Insights and Recurring pages meaningful with insufficient history", async () => {
    vi.spyOn(api, 'intelligence').mockResolvedValue(data);
    const view = render(<IntelligencePage page="insights"/>);
    expect(await screen.findByText(data.currencies[0].insights[0].text)).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'The rhythm of your spending' })).not.toBeInTheDocument();
    view.rerender(<IntelligencePage key="recurring" page="recurring"/>);
    expect(await screen.findByText('More history unlocks recurring patterns')).toBeVisible();
    expect(screen.queryByText('Estimated monthly pattern')).not.toBeInTheDocument();
});
it("plots exact high precision geometry with negative values and explicit gaps", async () => {
    const result = chartGeometry([{ month: '2026-07', value: '-999999999999999.9999' }, { month: '2026-08', value: null }, { month: '2026-09', value: '999999999999999.9999' }]);
    expect(result.zero).toBe(112);
    expect(result.points.map(p => p.y)).toEqual([184, null, 40]);
    render(<LineChart points={[{ month: '2026-07', value: '-10.0000' }, { month: '2026-09', value: '20.0000' }]} currency="AED" label="Net cash flow"/>);
    expect(screen.getByRole('button', { name: 'August 2026: No observation' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'July 2026: −10.00 AED' }));
    await waitFor(() => expect(screen.getAllByText('−10.00 AED').length).toBeGreaterThan(0));
});
