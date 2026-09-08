import { Protected } from "@/components/session";
import { Shell } from "@/components/shell";
import { UploadStatement } from "@/features/imports";
export default function Page() {
  return (
    <Protected>
      <Shell>
        <UploadStatement />
      </Shell>
    </Protected>
  );
}
