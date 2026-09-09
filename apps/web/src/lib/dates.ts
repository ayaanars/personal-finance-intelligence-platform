const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
export function monthLabel(value: string): string {
    const match = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(value);
    return match ? `${months[Number(match[2]) - 1]} ${match[1]}` : "Unavailable date";
}
export function dateLabel(value: string | null | undefined): string {
    if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value))
        return "Unavailable date";
    const parsed = new Date(`${value}T00:00:00Z`);
    if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value)
        return "Unavailable date";
    return `${Number(value.slice(8))} ${monthLabel(value.slice(0, 7))}`;
}
export function readableDates(text: string): string {
    return text.replace(/\b\d{4}-(?:0[1-9]|1[0-2])(?:-\d{2})?\b/g, value => value.length === 7 ? monthLabel(value) : dateLabel(value));
}
