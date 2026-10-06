import { useCallback, useEffect, useState } from "react";
import { alertsApi, type AlertStatus } from "../api";
import { Card } from "../components/AnalysisSections";
import { fmtWhen } from "../components/InfoTip";

export default function AlertsPage() {
  const [s, setS] = useState<AlertStatus | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    alertsApi.status().then((d) => { setS(d); setError(""); }).catch((e) => setError(String(e)));
  }, []);
  useEffect(() => { load(); }, [load]);

  const run = async (name: string, fn: () => Promise<{ ok: boolean; error: string | null }>, okText: string) => {
    setBusy(name);
    setResult(null);
    try {
      const r = await fn();
      setResult({ ok: r.ok, text: r.ok ? okText : `Failed: ${r.error}` });
    } catch (e) {
      setResult({ ok: false, text: String(e) });
    } finally {
      setBusy("");
      load();
    }
  };

  const checkStops = async () => {
    setBusy("stops");
    setResult(null);
    try {
      const { sent } = await alertsApi.checkStops();
      const failed = sent.filter((x) => !x.ok);
      setResult(failed.length
        ? { ok: false, text: `Failed: ${failed[0].error}` }
        : { ok: true, text: sent.length ? `Sent ${sent.length} stop alert(s).` : "No position has crossed a stop level that hasn't already been alerted." });
    } catch (e) {
      setResult({ ok: false, text: String(e) });
    } finally {
      setBusy("");
      load();
    }
  };

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold text-slate-900">Alerts</h1>
      {error && <p className="text-red-600 text-sm">{error}</p>}

      {s && (
        <Card title="Telegram" hint={s.configured ? `chat ${s.chat_id}` : "not connected"}>
          <div className="grid sm:grid-cols-3 gap-2 text-sm mb-4">
            <Pill ok={s.configured} label={s.configured ? "Bot + chat set in .env" : !s.token_set ? "TELEGRAM_BOT_TOKEN missing" : "TELEGRAM_CHAT_ID missing"} />
            <Pill ok={s.enabled} label={s.enabled ? "Scheduled alerts on" : "Scheduled alerts off (settings.yaml)"} />
            <Pill ok label={`Books: ${s.books.join(", ")}`} />
          </div>
          <ul className="text-sm text-slate-600 space-y-1 mb-4">
            <li>• Summaries on weekdays at <b>{s.summary_times.join(" and ")}</b> IST: open positions, P&L, stop used, POP, month ROI, signals.</li>
            <li>• Stop alerts at <b>{s.stop_levels.map((l) => `${l}%`).join(" and ")}</b> of the stop, checked every {s.stop_check_min} min in market hours. Each level fires once and re-arms when usage drops 10 points below it.</li>
          </ul>
          <div className="flex flex-wrap gap-2">
            <Btn disabled={!s.configured || !!busy} onClick={() => run("test", alertsApi.test, "Test message sent — check the channel.")}>
              {busy === "test" ? "Sending…" : "Send test"}
            </Btn>
            <Btn disabled={!s.configured || !!busy} onClick={() => run("summary", alertsApi.summary, "Summary sent.")}>
              {busy === "summary" ? "Building…" : "Send summary now"}
            </Btn>
            <Btn disabled={!s.configured || !!busy} onClick={checkStops}>
              {busy === "stops" ? "Checking…" : "Check stops now"}
            </Btn>
          </div>
          {result && <p className={`text-sm mt-3 ${result.ok ? "text-emerald-700" : "text-red-600"}`}>{result.text}</p>}
        </Card>
      )}

      {s && !s.configured && <Setup />}

      {s && (
        <Card title="Recent messages" hint="last 50 · newest first">
          {s.log.length === 0 ? <p className="text-sm text-slate-400 text-center py-4">Nothing sent yet.</p> : (
            <ul className="divide-y divide-slate-100">
              {s.log.map((m, i) => (
                <li key={i} className="py-2">
                  <div className="flex items-center gap-2 text-xs">
                    <span className={`px-1.5 rounded ${m.ok ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{m.ok ? "sent" : "failed"}</span>
                    <span className="text-slate-500 capitalize">{m.kind}</span>
                    <span className="text-slate-400">{fmtWhen(m.at)}</span>
                    {m.error && <span className="text-red-600">{m.error}</span>}
                  </div>
                  <details className="text-xs mt-1">
                    <summary className="cursor-pointer text-slate-500">message</summary>
                    <pre className="whitespace-pre-wrap font-sans text-slate-700 bg-slate-50 rounded p-2 mt-1">{m.text.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&")}</pre>
                  </details>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}

function Setup() {
  return (
    <Card title="Connect a Telegram channel">
      <ol className="text-sm text-slate-700 space-y-2 list-decimal pl-5">
        <li>In Telegram, open <b>@BotFather</b> → <code>/newbot</code> → pick a name and username → copy the <b>token</b>.</li>
        <li>Create a channel (or use yours) → <b>Manage channel → Administrators → Add admin</b> → search your bot → allow <b>Post messages</b>.</li>
        <li>
          Chat id: for a <b>public</b> channel use its username, e.g. <code>@my_option_alerts</code>. For a <b>private</b> channel, post any
          message in it, open <code>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code> and copy <code>"chat":{"{"}"id":-100…</code>.
        </li>
        <li>
          Add to <code>OPTIONDASHBOARD/.env</code> (copy <code>.env.example</code> if you have no .env):
          <pre className="bg-slate-50 rounded p-2 mt-1 text-xs">TELEGRAM_BOT_TOKEN=123456:ABC...{"\n"}TELEGRAM_CHAT_ID=@my_option_alerts</pre>
        </li>
        <li>Restart <code>python master.py</code>, come back here and press <b>Send test</b>.</li>
        <li>When the test arrives, set <code>alerts: enabled: true</code> in <code>config/settings.yaml</code> for the scheduled summaries and stop alerts.</li>
      </ol>
    </Card>
  );
}

function Pill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className={`rounded-lg px-3 py-2 ${ok ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"}`}>
      {ok ? "✓" : "○"} {label}
    </div>
  );
}

function Btn({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="px-3 py-1.5 text-sm rounded-lg border border-blue-600 text-blue-700 hover:bg-blue-50 disabled:opacity-40">
      {children}
    </button>
  );
}
