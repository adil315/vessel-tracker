import { Link } from 'react-router-dom';

export default function Navbar() {
  return (
    <nav className="glass sticky top-0 z-20 mb-6 flex items-center justify-between rounded-2xl border border-white/10 px-5 py-3">
      <Link to="/" className="flex items-center gap-3 text-slate-100 transition hover:text-cyan-300">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-500/15 text-cyan-300">
          <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-[1.8]" aria-hidden="true">
            <path d="M3 15.5c2.3-2.1 4.8-3.2 7.5-3.2s5.2 1.1 7.5 3.2" />
            <path d="M7 9.5h10M12 6v7" />
            <path d="M5 18.5h14" />
          </svg>
        </div>
        <span className="text-lg font-semibold tracking-[0.2em] text-white">VESSEL TRACKER</span>
      </Link>

      <div className="flex items-center gap-3">
        <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/40 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300">
          <span className="pulse-dot inline-block h-2.5 w-2.5 rounded-full bg-emerald-400" />
          System Online
        </span>
      </div>
    </nav>
  );
}
