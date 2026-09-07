import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LedgerX | Foundation",
  description: "LedgerX development foundation",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
