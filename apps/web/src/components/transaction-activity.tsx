import { displayMoney } from "@/lib/api";
import { dateLabel } from "@/lib/dates";

export type Activity = {
  merchant: string | null;
  normalized_description: string;
  raw_description: string;
  amount: string;
  currency: string;
  category: string;
  transaction_date: string;
};
/** Shared factual presentation for the product and explicitly synthetic public example. */
export function ActivitySummary({ activity }: { activity: Activity }) {
  return (
    <div className="activity-summary">
      <div className="activity-name">
        <strong>{activity.merchant ?? activity.normalized_description}</strong>
        <span>{activity.category}</span>
      </div>
      <div className="activity-value">
        <strong>{displayMoney(activity.amount, activity.currency)}</strong>
        <span>
          {dateLabel(activity.transaction_date)} ·{" "}
          {activity.amount.startsWith("-") ? "Outflow" : "Inflow"}
        </span>
      </div>
    </div>
  );
}
