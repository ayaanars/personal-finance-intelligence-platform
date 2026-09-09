import { PreviewStatement } from "@/features/imports";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PreviewStatement id={id} />;
}
