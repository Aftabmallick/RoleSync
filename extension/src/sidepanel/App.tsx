import React, { useEffect, useState } from 'react';
import { KeepaliveManager } from '../background/KeepaliveManager';
import { JDExtractedPayload, AppExtensionMessage } from '../types/messages';
import { ScoreCard, ScoreBreakdown } from './components/ScoreCard';
import { PdfPreview } from './components/PdfPreview';
import { AutofillProgress } from './components/AutofillProgress';

const BACKEND_API_URL = 'http://localhost:8000/api/v1';

export default function App() {
  const [keepaliveConnected, setKeepaliveConnected] = useState<boolean>(false);
  const [currentJd, setCurrentJd] = useState<JDExtractedPayload | null>(null);
  const [isTailoring, setIsTailoring] = useState<boolean>(false);
  const [tailorResult, setTailorResult] = useState<{
    score?: ScoreBreakdown;
    pdfBase64?: string;
  } | null>(null);
  const [autofillProgress, setAutofillProgress] = useState<{
    completed: number;
    total: number;
    current: string;
  } | null>(null);

  useEffect(() => {
    // 1. Establish persistent keepalive port connection
    let port: chrome.runtime.Port | null = null;
    try {
      port = chrome.runtime.connect({ name: KeepaliveManager.KEEPALIVE_PORT_NAME });
      setKeepaliveConnected(true);

      port.onDisconnect.addListener(() => {
        setKeepaliveConnected(false);
      });
    } catch (err) {
      console.error('[RoleSync UI] Port connection error:', err);
    }

    // 2. Query initial session checkpoint state
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.session) {
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

      // Listen for autofill progress messages
      const messageListener = (msg: AppExtensionMessage) => {
        if (msg.action === 'AUTOFILL_PROGRESS') {
          setAutofillProgress({
            completed: msg.payload.fieldsCompleted,
            total: msg.payload.totalFields,
            current: msg.payload.currentFieldSelector
          });
        }
      };
      chrome.runtime.onMessage.addListener(messageListener);

      return () => {
        if (port) port.disconnect();
        chrome.storage.onChanged.removeListener(storageListener);
        chrome.runtime.onMessage.removeListener(messageListener);
      };
    }

    return () => {
      if (port) port.disconnect();
    };
  }, []);

  const handleTriggerTailoring = async () => {
    if (!currentJd) return;
    setIsTailoring(true);
    setTailorResult(null);

    try {
      // 1. Post to async endpoint
      const postRes = await fetch(`${BACKEND_API_URL}/tailor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_role: currentJd.jobTitle,
          company_name: currentJd.companyName,
          raw_job_description: currentJd.rawText,
          required_years: 3.0
        })
      });

      if (!postRes.ok) {
        throw new Error(`Server returned ${postRes.status}`);
      }

      const { task_id } = await postRes.json();

      // 2. Poll for completion
      const interval = setInterval(async () => {
        try {
          const pollRes = await fetch(`${BACKEND_API_URL}/tailor/${task_id}`);
          if (pollRes.ok) {
            const data = await pollRes.json();
            if (data.status === 'COMPLETED') {
              clearInterval(interval);
              setIsTailoring(false);
              setTailorResult({
                score: data.ats_score,
                pdfBase64: data.pdf_base64
              });
            } else if (data.status === 'FAILED') {
              clearInterval(interval);
              setIsTailoring(false);
              alert(`Tailoring failed: ${data.error}`);
            }
          }
        } catch (pollErr) {
          console.error('[RoleSync UI] Polling error:', pollErr);
        }
      }, 1000);

    } catch (err) {
      console.error('[RoleSync UI] Failed to enqueue task:', err);
      setIsTailoring(false);
      alert('Could not connect to RoleSync backend. Ensure server is running on port 8000.');
    }
  };

  const handleExecuteAutofill = async () => {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs[0]?.id) return;

    setAutofillProgress({ completed: 0, total: 3, current: 'Initializing...' });

    const sampleMappings = [
      { selector: 'input[name*="name"], #name, input[id*="first_name"]', value: 'Alex Mercer', type: 'TEXT' },
      { selector: 'input[name*="email"], #email', value: 'alex@mercer.dev', type: 'TEXT' },
      { selector: 'input[name*="phone"], #phone', value: '+1 (555) 019-2834', type: 'TEXT' }
    ];

    chrome.tabs.sendMessage(tabs[0].id, {
      action: 'EXECUTE_DOM_AUTOFILL',
      correlationId: `autofill_${Date.now()}`,
      timestamp: Date.now(),
      payload: { mappings: sampleMappings, resumeDataUri: tailorResult?.pdfBase64 }
    } as AppExtensionMessage);
  };

  return (
    <div className="flex flex-col min-h-screen bg-slate-50 text-slate-800 font-sans">
      {/* Header */}
      <header className="p-4 border-b border-slate-200 bg-white flex items-center justify-between shadow-sm sticky top-0 z-10">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow">
            RS
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-900 leading-tight">RoleSync Copilot</h1>
            <p className="text-[11px] text-slate-500">Autonomous Recruiter v2.0</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 bg-slate-50 px-2 py-1 rounded-full border border-slate-200">
          <span
            className={`w-2 h-2 rounded-full ${
              keepaliveConnected ? 'bg-emerald-500 ring-2 ring-emerald-200' : 'bg-amber-400'
            }`}
          />
          <span className="text-[11px] font-semibold text-slate-600">
            {keepaliveConnected ? 'Active' : 'Standby'}
          </span>
        </div>
      </header>

      {/* Main Container */}
      <main className="p-4 flex-1 flex flex-col gap-4">
        {currentJd ? (
          <>
            {/* Job Header Card */}
            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-100">
                  {currentJd.atsProvider}
                </span>
                <span className="text-xs text-slate-400 font-mono">Parsed</span>
              </div>
              <h2 className="text-base font-bold text-slate-900">{currentJd.jobTitle}</h2>
              <p className="text-sm text-slate-600 font-medium">{currentJd.companyName}</p>

              <button
                className={`mt-2 w-full py-2.5 px-4 font-semibold text-sm rounded-lg shadow-sm transition-all focus:ring-2 focus:ring-offset-1 ${
                  isTailoring
                    ? 'bg-indigo-400 cursor-not-allowed text-white'
                    : 'bg-indigo-600 hover:bg-indigo-700 text-white focus:ring-indigo-500'
                }`}
                disabled={isTailoring}
                onClick={handleTriggerTailoring}
              >
                {isTailoring ? 'Verifying Guardrails & Tailoring...' : 'Tailor Resume & Calculate ATS Score'}
              </button>
            </div>

            {/* ATS Score Card */}
            {tailorResult?.score && <ScoreCard score={tailorResult.score} />}

            {/* PDF Preview */}
            {tailorResult?.pdfBase64 && (
              <PdfPreview
                pdfBase64={tailorResult.pdfBase64}
                onDownload={() => {
                  const link = document.createElement('a');
                  link.href = `data:application/pdf;base64,${tailorResult.pdfBase64}`;
                  link.download = 'RoleSync_Tailored_Resume.pdf';
                  link.click();
                }}
              />
            )}

            {/* Autofill Trigger & Progress */}
            {tailorResult && (
              <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col gap-3">
                <button
                  className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm rounded-lg shadow-sm transition-all focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1"
                  onClick={handleExecuteAutofill}
                >
                  Execute DOM Autofill & File Attachment
                </button>
                {autofillProgress && (
                  <AutofillProgress
                    completed={autofillProgress.completed}
                    total={autofillProgress.total}
                    currentSelector={autofillProgress.current}
                  />
                )}
              </div>
            )}
          </>
        ) : (
          <div className="p-8 bg-white rounded-xl border border-dashed border-slate-300 text-center flex flex-col items-center justify-center gap-3 flex-1">
            <div className="w-12 h-12 rounded-full bg-indigo-50 flex items-center justify-center text-indigo-600 text-xl font-bold">
              🔍
            </div>
            <h3 className="text-sm font-bold text-slate-800">Navigate to an ATS Career Portal</h3>
            <p className="text-xs text-slate-500 max-w-[240px] leading-relaxed">
              Open any Greenhouse, Lever, Workday, or LinkedIn job posting. RoleSync will automatically extract requirements.
            </p>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="p-3 border-t border-slate-200 bg-white text-center text-[11px] text-slate-400">
        RoleSync v2.0 • 4-Layer Guardrail & Single-Page Typst
      </footer>
    </div>
  );
}
