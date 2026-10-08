import { Link } from 'react-router-dom';

export default function LandingPage() {
  return (
    <div className="fade-enter flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-sky-950 to-slate-900 px-6">
      <div className="glass w-full max-w-[560px] rounded-2xl border border-white/10 p-10 text-center shadow-2xl shadow-cyan-950/30">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-white/5 text-cyan-300 shadow-lg shadow-cyan-500/10">
          <svg viewBox="0 0 64 64" className="h-10 w-10 fill-none stroke-current stroke-[2.2]" aria-hidden="true">
            <path d="M10 38c7-8 16-12 22-12 7 0 14 4 22 12" />
            <path d="M24 18h16v20H24z" opacity="0.7" />
            <path d="M22 44h20" />
            <path d="M12 54h40" />
          </svg>
        </div>

        <h1 className="text-4xl font-black uppercase tracking-[0.25em] text-white">VESSEL TRACKER</h1>
        <p className="mt-3 text-base text-slate-300">Subsea DAS vessel detection & tracking</p>
        <div className="mx-auto mt-5 h-0.5 w-24 bg-cyan-400" />

        <Link
          to="/dashboard"
          className="mt-8 inline-flex items-center justify-center rounded-xl bg-cyan-500 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-cyan-500/25 transition hover:bg-cyan-400 active:scale-[0.98]"
        >
          Launch Dashboard →
        </Link>

        <div className="mt-10 text-sm text-slate-400">© 2025 Vessel Tracker • Subsea Monitoring Platform</div>
      </div>
    </div>
  );
}
