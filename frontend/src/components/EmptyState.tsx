type EmptyStateProps = {
  title?: string;
  message?: string;
};

export default function EmptyState({ title = 'No data yet', message = 'Submit parameters to view vessel track' }: EmptyStateProps) {
  return (
    <div className="flex h-full min-h-[300px] items-center justify-center rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 text-center">
      <div>
        <p className="text-xl font-semibold text-slate-200">{title}</p>
        <p className="mt-2 text-sm text-slate-400">{message}</p>
      </div>
    </div>
  );
}
