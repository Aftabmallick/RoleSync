import React, { useEffect, useState } from 'react';
import { KeepaliveManager } from '../background/KeepaliveManager';
import { JDExtractedPayload } from '../types/messages';

export default function App() {
  const [keepaliveConnected, setKeepaliveConnected] = useState<boolean>(false);
  const [currentJd, setCurrentJd] = useState<JDExtractedPayload | null>(null);

  useEffect(() => {
    // 1. Establish persistent keepalive port connection to background service worker
    let port: chrome.runtime.Port | null = null;
    try {
      port = chrome.runtime.connect({ name: KeepaliveManager.KEEPALIVE_PORT_NAME });
      setKeepaliveConnected(true);
      console.log('[RoleSync UI] Keepalive port established.');

      port.onDisconnect.addListener(() => {
        setKeepaliveConnected(false);
        console.warn('[RoleSync UI] Keepalive port disconnected.');
      });
    } catch (err) {
      console.error('[RoleSync UI] Error establishing port:', err);
    }

    // 2. Query initial session checkpoint state
    if (chrome && chrome.storage && chrome.storage.session) {
      chrome.storage.session.get('current_jd').then((res) => {
        if (res.current_jd?.data) {
          setCurrentJd(res.current_jd.data);
        }
      });

      const storageListener = (changes: { [key: string]: chrome.storage.StorageChange }) => {
        if (changes.current_jd) {
          setCurrentJd(changes.current_jd.newValue?.data || null);
        }
      };
      chrome.storage.onChanged.addListener(storageListener);

      return () => {
        if (port) port.disconnect();
        chrome.storage.onChanged.removeListener(storageListener);
      };
    }

    return () => {
      if (port) port.disconnect();
    };
  }, []);

  return (
    <div className="flex flex-col min-h-screen bg-slate-50 text-slate-800">
      {/* Header */}
      <header className="p-4 border-b border-slate-200 bg-white flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow">
            RS
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 leading-tight">RoleSync</h1>
            <p className="text-xs text-slate-500">Autonomous Copilot v2.0</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              keepaliveConnected ? 'bg-emerald-500 ring-4 ring-emerald-100' : 'bg-amber-400'
            }`}
          />
          <span className="text-[11px] font-medium text-slate-500">
            {keepaliveConnected ? 'Live' : 'Standby'}
          </span>
        </div>
      </header>

      {/* Main Container */}
      <main className="p-4 flex-1 flex flex-col gap-4">
        {currentJd ? (
          <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                {currentJd.atsProvider}
              </span>
              <span className="text-xs text-slate-400 font-mono">Ready</span>
            </div>
            <h2 className="text-base font-bold text-slate-900">{currentJd.jobTitle}</h2>
            <p className="text-sm text-slate-600 font-medium">{currentJd.companyName}</p>

            <button
              className="mt-3 w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-lg shadow-sm transition-all focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
              onClick={() => alert('Tailoring pipeline triggered via Celery!')}
            >
              Tailor Resume with Zero-Hallucination
            </button>
          </div>
        ) : (
          <div className="p-6 bg-white rounded-xl border border-dashed border-slate-300 text-center flex flex-col items-center justify-center gap-2 flex-1">
            <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
              🔍
            </div>
            <h3 className="text-sm font-semibold text-slate-700">Navigate to an ATS Job Page</h3>
            <p className="text-xs text-slate-500 max-w-[220px]">
              Open any Greenhouse, Lever, Workday, or LinkedIn job posting to auto-extract details.
            </p>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="p-3 border-t border-slate-200 bg-white text-center text-[11px] text-slate-400">
        RoleSync v2.0 • 4-Layer Guardrail Active
      </footer>
    </div>
  );
}

