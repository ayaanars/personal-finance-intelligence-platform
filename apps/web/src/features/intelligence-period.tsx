"use client";
import { createContext, useContext, useState } from "react";
const Period = createContext<{
    month: string | undefined;
    currency: string;
    setMonth: (value: string | undefined) => void;
    setCurrency: (value: string) => void;
} | null>(null);
export function IntelligencePeriodProvider({ children }: {
    children: React.ReactNode;
}) {
    const [month, setMonth] = useState<string>();
    const [currency, setCurrency] = useState("");
    return <Period.Provider value={{ month, setMonth, currency, setCurrency }}>{children}</Period.Provider>;
}
export function useIntelligencePeriod() {
    const shared = useContext(Period);
    const [month, setMonth] = useState<string>();
    const [currency, setCurrency] = useState("");
    return shared ?? { month, setMonth, currency, setCurrency };
}
