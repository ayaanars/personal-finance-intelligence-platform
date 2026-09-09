import { Protected } from "@/components/session";
import { Shell } from "@/components/shell";
import { Overview } from "@/features/overview";
export default function Home() {
  return (
    <Protected>
      <Shell>
        <Overview />
      </Shell>
    </Protected>
  );
}
