import { Protected } from "@/components/session";
import { Shell } from "@/components/shell";
import { TransactionHistory } from "@/features/transactions";
export default function Home() {
  return (
    <Protected>
      <Shell>
        <TransactionHistory />
      </Shell>
    </Protected>
  );
}
