export default function ComingSoon({ title, phase }: { title: string; phase: number }) {
  return (
    <div className="bg-white border border-dashed border-slate-300 rounded-xl p-16 text-center">
      <h1 className="text-lg font-semibold text-slate-800">{title}</h1>
      <p className="text-slate-500 mt-1">Coming in phase {phase}.</p>
    </div>
  );
}
