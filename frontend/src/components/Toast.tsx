type ToastProps = {
  message: string;
  variant?: 'success' | 'error';
};

export default function Toast({ message, variant = 'success' }: ToastProps) {
  const palette =
    variant === 'error'
      ? 'border-red-500/40 bg-red-500/10 text-red-100'
      : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100';

  return (
    <div className={`pointer-events-none fixed right-5 top-5 z-50 max-w-sm rounded-xl border px-4 py-3 text-sm shadow-2xl ${palette}`}>
      {message}
    </div>
  );
}
