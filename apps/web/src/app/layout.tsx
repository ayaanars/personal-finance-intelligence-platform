import type { Metadata } from "next";
import "@fontsource-variable/geist";
import "./globals.css";
import "./public.css";
import "./overview.css";
import "./private.css";
import { SessionProvider } from "@/components/session";

export const metadata: Metadata = {
  title: "LedgerX | Personal financial intelligence",
  description:
    "Bring your transactions together and make sense of your everyday.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
