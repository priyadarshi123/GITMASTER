import { NavLink, Outlet } from "react-router-dom";
import { fmtTime } from "../api";
import { DashboardProvider, useDashboard } from "../useDashboard";

export default function Layout() {
  return (
    <DashboardProvider>
      <div className="min-h-screen flex flex-col">
        <Header />
        <ProviderBanner />
        <main className="flex-1 w-full max-w-[1400px] mx-auto px-4 sm:px-6 py-6">
          <Outlet />
        </main>
        <footer className="text-xs text-slate-400 text-center px-4 py-6 border-t border-slate-200">
          Market data and analytics for personal research only — not investment advice.
          Derivatives carry substantial risk.
        </footer>
      </div>
    </DashboardProvider>
  );
}

function Header() {
  const { data, refreshNow, notice } = useDashboard();
  const running = data?.refresh.running;
  const nav = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1.5 rounded-lg text-sm border transition ${
      isActive ? "border-brand text-brand" : "border-slate-600 text-slate-200 hover:border-slate-400"
    }`;

  return (
    <header className="bg-ink text-white">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-4 flex flex-wrap items-center gap-3">
        <NavLink to="/" className="flex items-center gap-2 mr-auto">
          <span className="grid place-items-center w-8 h-8 rounded-md bg-brand text-ink font-black">Ω</span>
          <span className="font-semibold tracking-wide text-brand text-lg">Option Dashboard</span>
        </NavLink>

        {data && (
          <span
            title={data.provider.note}
            className={`text-xs px-2 py-1 rounded-full border ${
              data.provider.live ? "border-emerald-500 text-emerald-300" : "border-amber-500 text-amber-300"
            }`}
          >
            ● {data.provider.live ? "Live · Angel One" : "Free · Yahoo + NSE"}
          </span>
        )}

        <button
          onClick={refreshNow}
          disabled={running}
          className="px-3 py-1.5 rounded-lg text-sm font-medium bg-brand text-ink disabled:opacity-60 hover:brightness-110"
          title={notice || "Fetch fresh prices and recompute signals"}
        >
          {running ? `Refreshing ${data?.refresh.step}…` : "↻ Refresh now"}
        </button>

        <nav className="flex gap-2">
          <NavLink to="/" end className={nav}>Dashboard</NavLink>
          <NavLink to="/positions/real" className={nav}>Positions</NavLink>
          <NavLink to="/guide" className={nav}>Guide</NavLink>
          <NavLink to="/alerts" className={nav}>Alerts</NavLink>
        </nav>
      </div>
      {(notice || data?.refresh.error) && (
        <div className="text-center text-xs py-1 bg-slate-800 text-amber-200">
          {notice || `Last refresh failed: ${data?.refresh.error}`}
        </div>
      )}
      {data && (
        <div className="sr-only" aria-live="polite">Data as of {fmtTime(data.asof)}</div>
      )}
    </header>
  );
}

function ProviderBanner() {
  const { data, error } = useDashboard();
  if (error)
    return (
      <Banner tone="red">
        <b>Backend not reachable.</b> Start it with <code>python master.py</code>. ({error})
      </Banner>
    );
  if (!data || data.provider.live) return null;
  return (
    <Banner tone="slate">
      {data.provider.note}. Margins are estimates; add Angel One keys in <code>.env</code> for live prices
      and exact margins (optional).
    </Banner>
  );
}

const BANNER_TONE = {
  slate: "bg-white border-slate-200 text-slate-600",
  red: "bg-red-50 border-red-300 text-red-900",
};

function Banner({ tone, children }: { tone: keyof typeof BANNER_TONE; children: React.ReactNode }) {
  const cls = BANNER_TONE[tone];
  return (
    <div className="max-w-[1400px] w-full mx-auto px-4 sm:px-6 pt-5 no-print">
      <div className={`border rounded-xl px-4 py-2 text-xs ${cls}`}>{children}</div>
    </div>
  );
}
