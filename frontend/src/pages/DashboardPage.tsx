import { useMemo, useState } from 'react';
import Navbar from '../components/Navbar';
import ParameterPanel from '../components/ParameterPanel';
import FibrePlot from '../components/FibrePlot';
import MapView from '../components/MapView';
import ScoreBadges from '../components/ScoreBadges';
import Toast from '../components/Toast';
import { submitTrack } from '../services/api';
import type { Algorithm, Cable, TrackResponse } from '../types';

const defaultForm = {
  cable: 's1' as Cable,
  algorithm: 'VITERBI-BEAM' as Algorithm,
  chain: 'Frequency tonality chain',
  table: 'subsea1_pids1predictedevents_2026_09_29',
  min_od: 22000,
  max_od: 75000,
  start_time: '2026-09-29T03:00',
  end_time: '2026-09-29T05:00',
  conf_min: 0,
  overlay_ais: false,
};

export default function DashboardPage() {
  const [form, setForm] = useState(defaultForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; variant: 'success' | 'error' } | null>(null);
  const [data, setData] = useState<TrackResponse | null>(null);
  const [hoveredPointIndex, setHoveredPointIndex] = useState<number | null>(null);
  const [mapType, setMapType] = useState<'Roadmap' | 'Satellite' | 'Hybrid'>('Roadmap');

  const primaryScore = useMemo(() => data?.tracks?.[0]?.score, [data]);

  const handleDownloadCsv = () => {
    if (!data?.tracks?.[0]?.points?.length) return;
    const rows = data.tracks[0].points;
    const headers = ['time', 'pos_km', 'z', 'on_lat', 'on_lon', 'boat_lat', 'boat_lon', 'h_smooth'];
    const csv = [
      headers.join(','),
      ...rows.map((row) => headers.map((header) => JSON.stringify((row as Record<string, any>)[header] ?? '')).join(',')),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'primary-track.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await submitTrack({
        ...form,
        min_od: Number(form.min_od),
        max_od: Number(form.max_od),
        conf_min: Number(form.conf_min),
      });
      setData(response);
      setToast({ message: `Loaded ${response.metadata?.total_detections ?? 0} detections`, variant: 'success' });
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Track request failed';
      setError(message);
      setToast({ message, variant: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 px-4 pb-6 pt-4 text-slate-50 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1500px]">
        <Navbar />

        {loading && (
          <div className="mb-4 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
            <div className="h-full w-1/2 animate-pulse bg-cyan-400" />
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
          <div className="lg:sticky lg:top-24 lg:self-start">
            <ParameterPanel
              form={form}
              setForm={setForm}
              onSubmit={handleSubmit}
              loading={loading}
              onReset={() => setForm(defaultForm)}
            />
          </div>

          <main className="space-y-6" aria-live="polite">
            <section className="glass rounded-2xl border border-white/10 p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="rounded-lg bg-cyan-500/15 p-2 text-cyan-300">📈</span>
                  <div>
                    <h2 className="text-xl font-semibold text-white">Fibre Distance vs Time</h2>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <ScoreBadges score={primaryScore} />
                  <button
                    type="button"
                    onClick={handleDownloadCsv}
                    className="rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-2 text-xs text-slate-200 hover:bg-slate-700/80"
                  >
                    Download CSV
                  </button>
                </div>
              </div>

              {error && (
                <div className="mb-4 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-red-100">
                  {error}
                </div>
              )}

              {data ? <FibrePlot data={data} hoveredPointIndex={hoveredPointIndex} onHoverPoint={setHoveredPointIndex} /> : <div className="h-[480px] rounded-2xl border border-dashed border-slate-700 bg-slate-900/30" />}
            </section>

            <section className="glass rounded-2xl border border-white/10 p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="rounded-lg bg-cyan-500/15 p-2 text-cyan-300">📍</span>
                  <div>
                    <h2 className="text-xl font-semibold text-white">Vessel Geographic Position</h2>
                  </div>
                </div>
                <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/70 p-1 text-xs">
                  {(['Roadmap', 'Satellite', 'Hybrid'] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setMapType(mode)}
                      className={`rounded-md px-3 py-1.5 transition ${mapType === mode ? 'bg-cyan-500 text-white' : 'text-slate-300 hover:bg-slate-700'}`}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>

              {data?.ais_available === false && data?.tracks?.length ? (
                <div className="mb-3 inline-flex rounded-full border border-slate-600 bg-slate-700/60 px-3 py-1 text-xs text-slate-300">
                  AIS unavailable for this window
                </div>
              ) : null}

              <MapView data={data ?? undefined} hoveredPointIndex={hoveredPointIndex} mapType={mapType} />
            </section>
          </main>
        </div>
      </div>

      {toast && <Toast message={toast.message} variant={toast.variant} />}
    </div>
  );
}
