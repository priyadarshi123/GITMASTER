import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, type Dashboard } from "./api";

interface Ctx {
  data: Dashboard | null;
  error: string;
  notice: string;
  reload: () => Promise<void>;
  refreshNow: () => Promise<void>;
  toggleBookmark: (symbol: string) => Promise<void>;
}

const DashboardContext = createContext<Ctx | null>(null);

const IDLE_POLL_MS = 60_000;   // pick up scheduler refreshes
const BUSY_POLL_MS = 2_000;    // while a refresh is running

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const timer = useRef<number | undefined>(undefined);

  const reload = useCallback(async () => {
    try {
      const d = await api.dashboard();
      setData(d);
      setError("");
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(reload, d.refresh.running ? BUSY_POLL_MS : IDLE_POLL_MS);
    } catch (e) {
      setError(String(e));
      timer.current = window.setTimeout(reload, IDLE_POLL_MS);
    }
  }, []);

  useEffect(() => {
    reload();
    return () => window.clearTimeout(timer.current);
  }, [reload]);

  const refreshNow = useCallback(async () => {
    const r = await api.refresh();
    setNotice(r.started ? "" : `Showing cached data — ${r.reason}`);
    if (!r.started) window.setTimeout(() => setNotice(""), 4000);
    await reload();
  }, [reload]);

  const toggleBookmark = useCallback(async (symbol: string) => {
    const { bookmarked } = await api.toggleBookmark(symbol);
    setData((d) => d && {
      ...d,
      items: d.items.map((i) => (i.symbol === symbol ? { ...i, bookmarked } : i)),
    });
  }, []);

  return (
    <DashboardContext.Provider value={{ data, error, notice, reload, refreshNow, toggleBookmark }}>
      {children}
    </DashboardContext.Provider>
  );
}

export function useDashboard() {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error("useDashboard outside DashboardProvider");
  return ctx;
}
