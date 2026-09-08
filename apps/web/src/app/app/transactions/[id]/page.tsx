import { Protected } from "@/components/session";
import { Shell } from "@/components/shell";
import { TransactionDetail } from "@/features/transactions";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <Protected>
      <Shell>
        <TransactionDetail id={id} />
      </Shell>
    </Protected>
  );
}
