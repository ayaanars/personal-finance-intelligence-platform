"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { announceSessionChange, useSession } from "./session";

export function Shell({ children }: { children: React.ReactNode }) {
  const { user, clear } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function logout() {
    setBusy(true);
    setError("");
    try {
      await api.logout();
      clear();
      announceSessionChange();
      router.replace("/login");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <a className="skip" href="#content">
        Skip to content
      </a>
      <header className="topbar">
        <Link href="/" className="brand">
          Ledger<span>X</span>
        </Link>
        <nav aria-label="Primary">
          <Link href="/app" aria-current={pathname === "/app" ? "page" : undefined}>
            Overview
          </Link>
          <Link
            aria-current={
              pathname.startsWith("/app/transactions")
                ? "page"
                : undefined
            }
            href="/app/transactions"
          >
            Transactions
          </Link>
          <Link
            aria-current={
              pathname.startsWith("/app/import") ? "page" : undefined
            }
            href="/app/import"
          >
            Import statement
          </Link>
        </nav>
        <div className="identity">
          <span>{user?.email}</span>
          <button
            className="text-button"
            disabled={busy}
            onClick={() => void logout()}
          >
            {busy ? "Signing out…" : "Log out"}
          </button>
        </div>
      </header>
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      <main id="content" className="workspace">
        {children}
      </main>
      <footer className="footer">
        Your financial history. A clearer perspective.
      </footer>
    </>
  );
}
