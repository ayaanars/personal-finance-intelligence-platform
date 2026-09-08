import { Protected } from "@/components/session";
import { Shell } from "@/components/shell";
import { PreviewStatement } from "@/features/imports";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <Protected>
      <Shell>
        <PreviewStatement id={id} />
      </Shell>
    </Protected>
  );
}
