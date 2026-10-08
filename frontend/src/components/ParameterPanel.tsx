import type { Dispatch, FormEvent, SetStateAction } from 'react';
import type { Algorithm, Cable } from '../types';

type FormState = {
  cable: Cable;
  algorithm: Algorithm;
  chain: string;
  table: string;
  min_od: number;
  max_od: number;
  start_time: string;
  end_time: string;
  conf_min: number;
  overlay_ais: boolean;
};

type ParameterPanelProps = {
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  loading: boolean;
  onReset: () => void;
};

const algos: Array<Algorithm> = ['ST-DBSCAN', 'RANSAC-CV', 'VGRAPH', 'SEED-GROW', 'SEED-GROW-KINEMATIC', 'VITERBI-BEAM', 'ALL'];

export default function ParameterPanel({ form, setForm, onSubmit, loading, onReset }: ParameterPanelProps) {
  const errors: string[] = [];
  if (form.start_time && form.end_time && new Date(form.start_time) >= new Date(form.end_time)) {
    errors.push('start_time must be earlier than end_time');
  }
  if (Number(form.min_od) >= Number(form.max_od)) {
    errors.push('min_od must be less than max_od');
  }
  if (!form.cable) {
    errors.push('cable is required');
  }
  if (Number.isNaN(Number(form.min_od)) || Number.isNaN(Number(form.max_od)) || Number.isNaN(Number(form.conf_min))) {
    errors.push('numeric values must parse as numbers');
  }

  return (
    <aside className="glass rounded-2xl border border-white/10 p-6">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">Track Parameters</h2>
        <span className="text-cyan-300">⚙️</span>
      </div>

      <form onSubmit={onSubmit} className="space-y-5">
        <div>
          <label className="mb-2 block text-[11px] uppercase tracking-[0.2em] text-slate-400">Cable</label>
          <div className="grid grid-cols-2 rounded-xl border border-slate-700 bg-slate-900/80 p-1">
            {(['s1', 's2'] as const).map((cable) => (
              <button
                key={cable}
                type="button"
                onClick={() => setForm((prev) => ({ ...prev, cable }))}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition ${form.cable === cable ? 'bg-cyan-500 text-white shadow-lg shadow-cyan-500/20' : 'text-slate-300 hover:bg-slate-800'}`}
              >
                {cable.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-2 block text-[11px] uppercase tracking-[0.2em] text-slate-400">Algorithm</label>
          <select
            value={form.algorithm}
            onChange={(e) => setForm((prev) => ({ ...prev, algorithm: e.target.value as Algorithm }))}
            className="w-full rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100 outline-none ring-0 transition focus:border-cyan-400"
          >
            {algos.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-2 block text-[11px] uppercase tracking-[0.2em] text-slate-400">Detection Chain</label>
          <select
            value={form.chain}
            onChange={(e) => setForm((prev) => ({ ...prev, chain: e.target.value }))}
            className="w-full rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-cyan-400"
          >
            <option>Frequency tonality chain</option>
            <option>Broadband chain</option>
            <option>CW chain</option>
            <option>Transient chain</option>
          </select>
        </div>

        <div>
          <label className="mb-2 block text-[11px] uppercase tracking-[0.2em] text-slate-400">Start Time</label>
          <input
            type="datetime-local"
            value={form.start_time}
            onChange={(e) => setForm((prev) => ({ ...prev, start_time: e.target.value }))}
            className="w-full rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-cyan-400"
          />
        </div>

        <div>
          <label className="mb-2 block text-[11px] uppercase tracking-[0.2em] text-slate-400">End Time</label>
          <input
            type="datetime-local"
            value={form.end_time}
            onChange={(e) => setForm((prev) => ({ ...prev, end_time: e.target.value }))}
            className="w-full rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-cyan-400"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-2 block text-[11px] uppercase tracking-[0.2em] text-slate-400">Min OD</label>
            <input
              type="number"
              value={form.min_od}
              onChange={(e) => setForm((prev) => ({ ...prev, min_od: Number(e.target.value) }))}
              className="w-full rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-cyan-400"
            />
          </div>
          <div>
            <label className="mb-2 block text-[11px] uppercase tracking-[0.2em] text-slate-400">Max OD</label>
            <input
              type="number"
              value={form.max_od}
              onChange={(e) => setForm((prev) => ({ ...prev, max_od: Number(e.target.value) }))}
              className="w-full rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-cyan-400"
            />
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <label className="block text-[11px] uppercase tracking-[0.2em] text-slate-400">Event Table</label>
            <span className="text-[10px] text-slate-400">ⓘ PostgreSQL table name</span>
          </div>
          <input
            type="text"
            value={form.table}
            onChange={(e) => setForm((prev) => ({ ...prev, table: e.target.value }))}
            className="w-full rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2.5 font-mono text-sm text-slate-100 outline-none focus:border-cyan-400"
          />
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between text-[11px] uppercase tracking-[0.2em] text-slate-400">
            <label>Confidence Min</label>
            <span>{form.conf_min.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={form.conf_min}
            onChange={(e) => setForm((prev) => ({ ...prev, conf_min: Number(e.target.value) }))}
            className="w-full accent-cyan-500"
          />
        </div>

        <div className="flex items-center justify-between rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2.5">
          <span className="text-sm text-slate-200">Overlay AIS / GPX</span>
          <button
            type="button"
            aria-label="toggle AIS overlay"
            onClick={() => setForm((prev) => ({ ...prev, overlay_ais: !prev.overlay_ais }))}
            className={`relative h-7 w-12 rounded-full border transition ${form.overlay_ais ? 'border-cyan-400 bg-cyan-500' : 'border-slate-600 bg-slate-700'}`}
          >
            <span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition ${form.overlay_ais ? 'left-6' : 'left-1'}`} />
          </button>
        </div>

        {errors.length > 0 && (
          <div className="space-y-1 text-sm text-red-300">
            {errors.map((message) => (
              <div key={message}>{message}</div>
            ))}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-xl bg-gradient-to-r from-cyan-500 to-blue-500 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-cyan-500/20 transition hover:from-cyan-400 hover:to-blue-400 disabled:cursor-not-allowed disabled:opacity-70 active:scale-[0.98]"
        >
          {loading ? 'Processing…' : 'Track Vessel'}
        </button>

        <button type="button" onClick={onReset} className="block w-full text-center text-sm text-slate-400 hover:text-slate-200">
          Reset to defaults
        </button>
      </form>
    </aside>
  );
}
