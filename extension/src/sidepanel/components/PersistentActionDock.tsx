import React from 'react';

interface PersistentActionDockProps {
  currentJd: {
    companyName: string;
    jobTitle: string;
    atsProvider?: string;
  } | null;
  executionMode: 'copilot' | 'autopilot';
  onModeChange: (mode: 'copilot' | 'autopilot') => void;
  onExecuteAutofill: () => void;
  onExecuteAutopilot: () => void;
  isAutopilotRunning: boolean;
  autofillProgress: { completed: number; total: number; current?: string } | null;
  hasTailoredResume: boolean;
}

export const PersistentActionDock: React.FC<PersistentActionDockProps> = ({
  currentJd,
  executionMode,
  onModeChange,
  onExecuteAutofill,
  onExecuteAutopilot,
  isAutopilotRunning,
  autofillProgress,
  hasTailoredResume,
}) => {
  if (!currentJd) return null;

  return (
    <div className="sticky bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-slate-200 p-3 shadow-lg flex flex-col gap-2">
      {/* Autofill in-flight progress bar */}
      {autofillProgress && autofillProgress.total > 0 && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between text-[11px] font-semibold text-slate-700">
            <span>Autofilling Form Fields...</span>
            <span className="text-emerald-600 font-bold">
              {autofillProgress.completed} / {autofillProgress.total}
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-emerald-500 h-1.5 rounded-full transition-all duration-300"
              style={{
                width: `${Math.round((autofillProgress.completed / autofillProgress.total) * 100)}%`,
              }}
            />
          </div>
        </div>
      )}

      <div className="flex items-center justify-between gap-2">
        {/* Mode Toggle Capsule */}
        <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200 shrink-0">
          <button
            onClick={() => onModeChange('copilot')}
            className={`px-2 py-1 text-[11px] font-semibold rounded-md transition-all ${
              executionMode === 'copilot'
                ? 'bg-white text-indigo-700 shadow-2xs font-bold'
                : 'text-slate-500 hover:text-slate-800'
            }`}
            title="Assisted 1-Click Autofill"
          >
            Copilot
          </button>
          <button
            onClick={() => onModeChange('autopilot')}
            className={`px-2 py-1 text-[11px] font-semibold rounded-md transition-all ${
              executionMode === 'autopilot'
                ? 'bg-white text-indigo-700 shadow-2xs font-bold'
                : 'text-slate-500 hover:text-slate-800'
            }`}
            title="Autonomous Workday Traversal"
          >
            Autopilot
          </button>
        </div>

        {/* Primary CTA */}
        {executionMode === 'copilot' ? (
          <button
            onClick={onExecuteAutofill}
            className="flex-1 py-2 px-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg shadow-sm transition-all focus:ring-2 focus:ring-emerald-500 flex items-center justify-center gap-1.5 active:scale-[0.99]"
          >
            <span>⚡ 1-Click Autofill</span>
            {hasTailoredResume && (
              <span className="text-[10px] bg-emerald-700 px-1.5 py-0.2 rounded font-normal">
                +Resume
              </span>
            )}
          </button>
        ) : (
          <button
            onClick={onExecuteAutopilot}
            disabled={isAutopilotRunning}
            className="flex-1 py-2 px-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-lg shadow-sm transition-all focus:ring-2 focus:ring-indigo-500 flex items-center justify-center gap-1.5 disabled:opacity-50 active:scale-[0.99]"
          >
            <span>
              {isAutopilotRunning ? '⏳ Traversing Portal...' : '🚀 Run Workday Autopilot'}
            </span>
          </button>
        )}
      </div>
    </div>
  );
};

