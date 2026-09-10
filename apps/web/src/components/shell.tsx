"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { announceSessionChange, useSession } from "./session";
export function Shell({ children }: {
    children: React.ReactNode;
}) {
    const { user, clear } = useSession();
    const pathname = usePathname();
    const router = useRouter();
    const [menu, setMenu] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    async function logout() { setBusy(true); setError(""); try {
        await api.logout();
        clear();
        announceSessionChange();
        router.replace("/login");
    }
    catch (e) {
        setError(errorMessage(e));
    }
    finally {
        setBusy(false);
    } }
    const groups = [
        { name: "Intelligence", links: [["/app", "Overview", "◈"], ["/app/insights", "Insights", "✦"], ["/app/trends", "Trends", "↗"], ["/app/unusual", "Unusual activity", "◇"], ["/app/relationships", "Relationships", "⋈"], ["/app/recurring", "Recurring", "↻"], ["/app/behaviour", "Behaviour", "≋"]] },
        { name: "Data", links: [["/app/transactions", "Transactions", "☷"], ["/app/import", "Import statement", "+"]] },
    ];
    const links = groups.flatMap(group => group.links);
    const current = links.find(([href]) => href === "/app" ? pathname === href : pathname.startsWith(href))?.[1] ?? "Workspace";
    return <div className="private-app">
  <a className="skip" href="#content">Skip to content</a>
  <aside className="app-rail"><Link href="/app" className="brand">Ledger<span>X</span></Link><span className="rail-caption">PERSONAL INTELLIGENCE</span>
   <button className="mobile-menu" aria-expanded={menu} aria-controls="private-navigation" onClick={() => setMenu(!menu)}>Explore / {current}<span aria-hidden="true">{menu ? "−" : "+"}</span></button>
   <nav id="private-navigation" className={menu ? "rail-nav open" : "rail-nav"} aria-label="Primary">{groups.map(group => <div className="rail-group" role="group" aria-label={group.name} key={group.name}><span className="rail-group-label">{group.name}</span>{group.links.map(([href, label, icon]) => <Link key={href} href={href} onClick={() => setMenu(false)} aria-current={label === current ? "page" : undefined}><span aria-hidden="true" className="nav-icon">{icon}</span>{label}</Link>)}</div>)}</nav>
   <div className="rail-bottom"><span className="rail-monogram" aria-hidden="true">LX</span><div><strong>Your private workspace</strong><span className="rail-email">{user?.email}</span></div></div>
  </aside>
  <div className="app-body"><header className="app-topline"><span>My workspace <span aria-hidden="true">/</span> <strong>{current}</strong></span><div className="topline-actions"><Link href="/app/import">Add history <span aria-hidden="true">↗</span></Link><button className="text-button" disabled={busy} onClick={() => void logout()}>{busy ? "Signing out…" : "Log out"}</button></div></header>
   {error && <p className="notice error" role="alert">{error}</p>}<main id="content" className="workspace">{children}</main><footer className="app-footer">Your history. Your perspective.<span>LedgerX</span></footer>
  </div>
 </div>;
}
