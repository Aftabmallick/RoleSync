import React, { useEffect } from 'react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastMessage {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
}

interface ToastContainerProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none px-4">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={() => onDismiss(toast.id)} />
      ))}
    </div>
  );
};

const ToastItem: React.FC<{ toast: ToastMessage; onDismiss: () => void }> = ({ toast, onDismiss }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss();
    }, toast.duration || 4000);
    return () => clearTimeout(timer);
  }, [toast, onDismiss]);

  const typeConfig = {
    success: {
      border: 'border-emerald-300',
      bg: 'bg-emerald-50 text-emerald-900',
      iconBg: 'bg-emerald-500 text-white',
      icon: '✓',
    },
    error: {
      border: 'border-rose-300',
      bg: 'bg-rose-50 text-rose-900',
      iconBg: 'bg-rose-500 text-white',
      icon: '✕',
    },
    warning: {
      border: 'border-amber-300',
      bg: 'bg-amber-50 text-amber-900',
      iconBg: 'bg-amber-500 text-white',
      icon: '⚠',
    },
    info: {
      border: 'border-indigo-300',
      bg: 'bg-indigo-50 text-indigo-900',
      iconBg: 'bg-indigo-500 text-white',
      icon: 'ℹ',
    },
  }[toast.type];

  return (
    <div
      className={`pointer-events-auto p-3 rounded-xl border shadow-lg flex items-start gap-3 transition-all transform translate-y-0 ${typeConfig.bg} ${typeConfig.border}`}
      role="alert"
    >
      <div
        className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 ${typeConfig.iconBg}`}
      >
        {typeConfig.icon}
      </div>
      <div className="flex-1 min-w-0">
        {toast.title && <div className="text-xs font-bold leading-snug">{toast.title}</div>}
        <div className="text-[11px] leading-relaxed break-words font-medium">{toast.message}</div>
      </div>
      <button
        onClick={onDismiss}
        className="text-slate-400 hover:text-slate-600 font-bold text-xs p-1 rounded hover:bg-black/5 transition-colors shrink-0"
        aria-label="Close"
      >
        ✕
      </button>
    </div>
  );
};

