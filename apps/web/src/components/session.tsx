"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
} from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, errorMessage, type User } from "@/lib/api";

const Session = createContext<{
  user: User | null;
  loading: boolean;
  error: string;
  refresh: () => Promise<void>;
  clear: () => void;
}>({
  user: null,
  loading: true,
  error: "",
  refresh: async () => {},
  clear: () => {},
});
export const useSession = () => useContext(Session);
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const generation = useRef({ value: 0 });
  const clear = useCallback(() => {
    generation.current.value++;
    setUser(null);
    setLoading(false);
  }, []);
  const restore = useCallback(() => {
    const current = ++generation.current.value;
    return api
      .me()
      .then((next) => {
        if (current === generation.current.value) {
          setUser(next);
          setError("");
        }
      })
      .catch((e: unknown) => {
        if (current === generation.current.value) {
          setUser(null);
          setError(
            e instanceof ApiError && e.status === 401
              ? "Your session has ended. Sign in again to continue."
              : errorMessage(e),
          );
        }
      })
      .finally(() => {
        if (current === generation.current.value) setLoading(false);
      });
  }, []);
  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    await restore();
  }, [restore]);
  useEffect(() => {
    const tracking = generation.current;
    const current = ++tracking.value;
    api
      .me()
      .then((next) => {
        if (current === tracking.value) setUser(next);
      })
      .catch((e: unknown) => {
        if (
          current === tracking.value &&
          !(e instanceof ApiError && e.status === 401)
        )
          setError(errorMessage(e));
      })
      .finally(() => {
        if (current === tracking.value) setLoading(false);
      });
    const expired = () => {
      clear();
      setError("Your session has ended. Sign in again to continue.");
    };
    const changed = () => {
      clear();
      void refresh();
    };
    const channel = new BroadcastChannel("ledgerx-session");
    channel.onmessage = changed;
    const visible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    window.addEventListener("ledgerx:unauthorized", expired);
    window.addEventListener("pageshow", changed);
    document.addEventListener("visibilitychange", visible);
    return () => {
      tracking.value++;
      channel.close();
      window.removeEventListener("ledgerx:unauthorized", expired);
      window.removeEventListener("pageshow", changed);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [refresh, clear]);
  return (
    <Session.Provider value={{ user, loading, error, refresh, clear }}>
      {children}
    </Session.Provider>
  );
}
export function announceSessionChange() {
  const channel = new BroadcastChannel("ledgerx-session");
  channel.postMessage("changed");
  channel.close();
}
export function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading, error, refresh } = useSession();
  const router = useRouter();
  useEffect(() => {
    if (!loading && !user && (!error || error.includes("session has ended")))
      router.replace("/login");
  }, [user, loading, error, router]);
  if (loading && !user)
    return (
      <div className="loading" role="status">
        Opening your workspace…
      </div>
    );
  if (!user)
    return (
      <div className="empty">
        <h1>Let’s reconnect</h1>
        <p role="alert">{error || "Taking you to sign in…"}</p>
        <button onClick={() => void refresh()}>Retry connection</button>
      </div>
    );
  return (
    <>
      <div key={user.id} hidden={loading}>
        {children}
      </div>
      {loading && (
        <div className="loading" role="status">
          Checking your session…
        </div>
      )}
    </>
  );
}
