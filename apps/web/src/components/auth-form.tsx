"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { announceSessionChange, useSession } from "./session";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { user, loading, error: sessionError, refresh } = useSession();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [registered, setRegistered] = useState(false);
  const register = mode === "register" && !registered;
  useEffect(() => {
    if (user && !loading) router.replace("/app");
  }, [user, loading, router]);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    // Read submitted controls so browser/password-manager autofill is honored even
    // when it does not dispatch React's change event. Native form validation runs first.
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const submittedEmail = String(form.get("email") ?? "");
    const submittedPassword = String(form.get("password") ?? "");
    setBusy(true);
    setError("");
    try {
      await api.credentials(
        register ? "register" : "login",
        submittedEmail,
        submittedPassword,
      );
      setPassword("");
      if (register) {
        setRegistered(true);
        await api.credentials("login", submittedEmail, submittedPassword);
        announceSessionChange();
        await refresh();
      } else {
        announceSessionChange();
        await refresh();
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  if (loading || user)
    return (
      <main className="loading" role="status">
        Checking your session…
      </main>
    );
  return (
    <main className="auth-page">
      <section className="auth-story">
        <Link href="/" className="brand">
          Ledger<span>X</span>
        </Link>
        <div>
          <p className="eyebrow">A clearer financial picture</p>
          <h1>
            Make sense of
            <br />
            your everyday.
          </h1>
          <p>
            Bring your transactions together. Understand the merchants. Make the
            categories your own.
          </p>
        </div>
        <p className="muted">
          Built around your history, one statement at a time.
        </p>
      </section>
      <section className="auth-panel">
        <div className="auth-form">
          <p className="eyebrow">Your private workspace</p>
          <h2>{register ? "Start with clarity." : "Welcome back."}</h2>
          <p>
            {register
              ? "Create an account to begin your transaction history."
              : "Sign in to pick up where you left off."}
          </p>
          {registered && (
            <p className="notice" role="status">
              Account created. If sign-in did not complete, enter your password
              to continue.
            </p>
          )}
          {(error || sessionError) && (
            <p id="auth-error" className="notice error" role="alert">
              {error || sessionError}
            </p>
          )}
          <form
            onSubmit={submit}
            aria-describedby={error ? "auth-error" : undefined}
          >
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              maxLength={320}
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={busy}
            />
            <label htmlFor="password">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete={register ? "new-password" : "current-password"}
              minLength={15}
              maxLength={128}
              aria-describedby="password-help"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
            />
            <p id="password-help" className="hint">
              15–128 characters. Spaces are welcome.
            </p>
            <button className="primary full" disabled={busy}>
              {busy ? "Please wait…" : register ? "Create account" : "Sign in"}
            </button>
          </form>
          <p className="auth-switch">
            {register ? "Already have an account?" : "New to LedgerX?"}{" "}
            <Link href={register ? "/login" : "/register"}>
              {register ? "Sign in" : "Create account"}
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
