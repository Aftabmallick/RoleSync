import React from 'react';

interface AutofillProgressProps {
  completed: number;
  total: number;
  currentSelector: string;
}

export const AutofillProgress: React.FC<AutofillProgressProps> = ({ completed, total, currentSelector }) => {
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col gap-2">
      <div className="flex items-center justify-between text-xs font-semibold">
        <span className="text-slate-700">Autofill Progress</span>
        <span className="text-indigo-600">{completed} / {total} fields ({percent}%)</span>
      </div>

      <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
        <div
          className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>

      <p className="text-[11px] text-slate-500 font-mono truncate">
        {currentSelector === 'DONE' ? 'Form autofill finished.' : `Target: ${currentSelector}`}
      </p>
    </div>
  );
};
