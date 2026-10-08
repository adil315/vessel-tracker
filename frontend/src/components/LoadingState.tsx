export default function LoadingState() {
  return (
    <div className="glass w-full rounded-2xl p-6">
      <div className="mb-4 h-5 w-40 animate-pulse rounded bg-slate-700/80" />
      <div className="h-72 animate-pulse rounded-xl bg-slate-800/70" />
    </div>
  );
}
