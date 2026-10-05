"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { announceSessionChange, useSession } from "./session";

export function PasswordRecovery({ complete = false }: { complete?: boolean }) {
  const token = useRef("");
  const { refresh } = useSession();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (complete && window.location.hash) {
      token.current = new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, [complete]);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setBusy(true);
    setError("");
    try {
      if (complete) {
        if (!token.current) throw new Error("missing token");
        await api.completeReset(token.current, String(fields.get("password") || ""));
        token.current = "";
        form.reset();
        announceSessionChange();
        await refresh();
        setMessage("Password updated. All previous sessions are signed out. Sign in with your new password.");
      } else {
        const result = await api.requestReset(String(fields.get("email") || ""));
        setMessage(result.message);
      }
      setDone(true);
    } catch (cause) {
      setError(complete && !token.current ? "Open a valid reset link to continue." : errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  return <main className="auth-page"><section className="auth-panel"><div className="auth-form">
    <Link className="brand" href="/">Ledger<span>X</span></Link>
    <h1>{complete ? "Choose a new password" : "Reset your password"}</h1>
    <p>{complete ? "Use 15–128 characters. Spaces are welcome." : "Enter your account email to request a one-time reset link."}</p>
    {error && <p className="notice error" role="alert">{error}</p>}
    {message && <p className="notice" role="status">{message}</p>}
    {!done && <form onSubmit={submit}>
      <label htmlFor="recovery-input">{complete ? "New password" : "Email address"}</label>
      <input id="recovery-input" name={complete ? "password" : "email"} type={complete ? "password" : "email"}
        autoComplete={complete ? "new-password" : "email"} required minLength={complete ? 15 : undefined}
        maxLength={complete ? 128 : 320} disabled={busy}/>
      <button className="primary full" disabled={busy}>{busy ? "Please wait…" : complete ? "Update password" : "Send reset link"}</button>
    </form>}
    <p><Link href="/login">Back to sign in</Link></p>
  </div></section></main>;
}
