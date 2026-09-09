import { TransactionDetail } from "@/features/transactions";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <TransactionDetail id={id} />;
}
