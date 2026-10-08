type ScoreBadgesProps = {
  score?: { mae_km?: number; n?: number; v_mean?: number };
};

export default function ScoreBadges({ score }: ScoreBadgesProps) {
  if (!score) return null;

  return (
    <div className="flex items-center gap-2 text-xs text-slate-300">
      {typeof score.mae_km === 'number' && (
        <span className="rounded-full border border-slate-600/60 bg-slate-800/70 px-2 py-1">MAE {score.mae_km.toFixed(2)} km</span>
      )}
      {typeof score.n === 'number' && (
        <span className="rounded-full border border-slate-600/60 bg-slate-800/70 px-2 py-1">N points {score.n}</span>
      )}
      {typeof score.v_mean === 'number' && (
        <span className="rounded-full border border-slate-600/60 bg-slate-800/70 px-2 py-1">V_mean {score.v_mean.toFixed(2)}</span>
      )}
    </div>
  );
}
