import { Protected } from "@/components/session";
import { Shell } from "@/components/shell";
import { IntelligencePeriodProvider } from "@/features/intelligence-period";
export default function PrivateLayout({ children }: {
    children: React.ReactNode;
}) {
    return <Protected><IntelligencePeriodProvider><Shell>{children}</Shell></IntelligencePeriodProvider></Protected>;
}
