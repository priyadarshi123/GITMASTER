import { useCallback, useEffect, useState } from "react";
import { analysisApi, type Note } from "../api";
import { useDashboard } from "../useDashboard";
import { Card } from "./AnalysisSections";
import { ana } from "../info";

export default function Notes({ symbol }: { symbol: string }) {
  const { reload } = useDashboard();
  const [notes, setNotes] = useState<Note[]>([]);
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState<{ id: number; text: string } | null>(null);

  const load = useCallback(() => analysisApi.notes(symbol).then(setNotes), [symbol]);
  useEffect(() => { load(); }, [load]);

  const changed = async () => {
    await load();
    reload();   // dashboard note-count badges
  };

  const add = async () => {
    if (!draft.trim()) return;
    await analysisApi.addNote(symbol, draft);
    setDraft("");
    changed();
  };

  return (
    <Card title="Notes" hint={`your dated journal for ${symbol}`} info={ana.notes()}>
      <div className="flex gap-3 items-start no-print">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && e.ctrlKey && add()}
          placeholder="e.g. Took support at S1 — stop as per risk:reward. Results on 7th, trade after."
          className="flex-1 min-h-[70px] border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200"
        />
        <button onClick={add} className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium">Add note</button>
      </div>
      {notes.length === 0 ? (
        <p className="text-sm text-slate-400 mt-3">No notes yet for {symbol}.</p>
      ) : (
        <ul className="mt-4 space-y-2">
          {notes.map((n) => (
            <li key={n.id} className="border border-slate-100 rounded-lg px-3 py-2">
              <div className="flex items-center gap-3 text-xs text-slate-400 mb-1">
                <span>{new Date(n.note_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</span>
                <span className="ml-auto flex gap-3 no-print">
                  <button className="hover:text-slate-700" onClick={() => setEditing({ id: n.id, text: n.text })}>Edit</button>
                  <button
                    className="hover:text-red-600"
                    onClick={async () => { await analysisApi.deleteNote(n.id); changed(); }}
                  >
                    Delete
                  </button>
                </span>
              </div>
              {editing?.id === n.id ? (
                <div className="flex gap-2">
                  <textarea
                    value={editing.text}
                    onChange={(e) => setEditing({ ...editing, text: e.target.value })}
                    className="flex-1 border border-slate-200 rounded px-2 py-1 text-sm"
                  />
                  <div className="flex flex-col gap-1">
                    <button
                      className="px-3 py-1 rounded bg-blue-600 text-white text-xs"
                      onClick={async () => { await analysisApi.editNote(n.id, editing.text); setEditing(null); changed(); }}
                    >
                      Save
                    </button>
                    <button className="px-3 py-1 rounded border text-xs" onClick={() => setEditing(null)}>Cancel</button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-700 whitespace-pre-wrap">{n.text}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
