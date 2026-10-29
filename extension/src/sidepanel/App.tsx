import { useEffect, useState } from 'react';
import { KeepaliveManager } from '../background/KeepaliveManager';
import { JDExtractedPayload, AppExtensionMessage } from '../types/messages';
import { ScoreCard, ScoreBreakdown } from './components/ScoreCard';
import { PdfPreview } from './components/PdfPreview';
import { AutofillProgress } from './components/AutofillProgress';
import { ProfileEditor, MasterProfileData } from './components/ProfileEditor';

const BACKEND_API_URL = 'http://localhost:8000/api/v1';

interface OutreachDraft {
  subject: string;
  body_text: string;
  word_count: number;
  recipient_email: string;
  opt_out_link: string;
  physical_address: string;
  is_compliant: boolean;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'copilot' | 'profile'>('copilot');
  const [masterProfile, setMasterProfile] = useState<MasterProfileData | null>(null);
  const [keepaliveConnected, setKeepaliveConnected] = useState<boolean>(false);
  const [currentJd, setCurrentJd] = useState<JDExtractedPayload | null>(null);
  const [isTailoring, setIsTailoring] = useState<boolean>(false);
  const [tailorStage, setTailorStage] = useState<string>('');
  const [tailorResult, setTailorResult] = useState<{
    score?: ScoreBreakdown;
    pdfBase64?: string;
  } | null>(null);
  const [autofillProgress, setAutofillProgress] = useState<{
    completed: number;
    total: number;
    current: string;
  } | null>(null);

  // Outreach synthesizer states
  const [outreachDraft, setOutreachDraft] = useState<OutreachDraft | null>(null);
  const [isGeneratingOutreach, setIsGeneratingOutreach] = useState<boolean>(false);
  const [outreachCopied, setOutreachCopied] = useState<boolean>(false);

  // Manual JD Tester states
  const [showManualJdModal, setShowManualJdModal] = useState<boolean>(false);
  const [manualTitle, setManualTitle] = useState<string>('');
  const [manualCompany, setManualCompany] = useState<string>('');
  const [manualText, setManualText] = useState<string>('');

  // Active tab scanning state
  const [isScanningTab, setIsScanningTab] = useState<boolean>(false);
  const [scanMessage, setScanMessage] = useState<string | null>(null);

  const handleScanCurrentTab = async () => {
    setIsScanningTab(true);
    setScanMessage('Scanning active tab for job posting...');

    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const activeTab = tabs[0];
      if (!activeTab?.id) {
        setScanMessage('No active browser tab found.');
        setIsScanningTab(false);
        return;
      }

      // 1. Try sending message to content script
      chrome.tabs.sendMessage(activeTab.id, { action: 'TRIGGER_PAGE_EXTRACTION' }, async (response) => {
        if (chrome.runtime.lastError || !response) {
          // If content script was not yet loaded (e.g. page was loaded before extension was installed), inject dynamically
          try {
            await chrome.scripting.executeScript({
              target: { tabId: activeTab.id! },
              files: ['dist/content/injector.js']
            });
            setTimeout(async () => {
              const res = await chrome.storage.session.get('current_jd');
              if (res.current_jd?.data) {
                setCurrentJd(res.current_jd.data);
                setScanMessage(`✓ Detected: ${res.current_jd.data.jobTitle}`);
              } else {
                setScanMessage('Scanned page. If not detected, paste JD below.');
              }
              setIsScanningTab(false);
            }, 1200);
          } catch (injectErr) {
            console.warn('[RoleSync UI] Script injection failed:', injectErr);
            setScanMessage('Cannot scan protected chrome:// pages. Navigate to a career portal.');
            setIsScanningTab(false);
          }
        } else {
          setTimeout(async () => {
            const res = await chrome.storage.session.get('current_jd');
            if (res.current_jd?.data) {
              setCurrentJd(res.current_jd.data);
              setScanMessage(`✓ Detected: ${res.current_jd.data.jobTitle}`);
            }
            setIsScanningTab(false);
          }, 800);
        }
      });
    } catch (e) {
      console.error('[RoleSync UI] Tab scan error:', e);
      setScanMessage('Error scanning tab.');
      setIsScanningTab(false);
    }
  };

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

    // 2. Query initial session checkpoint state & stored master profile
    if (typeof chrome !== 'undefined' && chrome.storage) {
      if (chrome.storage.local) {
        chrome.storage.local.get('rolesync_master_profile', (res) => {
          if (res.rolesync_master_profile) {
            setMasterProfile(res.rolesync_master_profile);
          }
        });
      }

      if (chrome.storage.session) {
        chrome.storage.session.get('current_jd').then((res) => {
          if (res.current_jd?.data) {
            setCurrentJd(res.current_jd.data);
          }
        }).catch(() => {});

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
    }

    return () => {
      if (port) port.disconnect();
    };
  }, []);

  const handleTriggerTailoring = async () => {
    if (!currentJd) return;
    setIsTailoring(true);
    setTailorStage('INITIALIZING');
    setTailorResult(null);
    setOutreachDraft(null);

    try {
      // Ensure masterProfile has experience with bullets so Layer 1 Schema check succeeds
      const effectiveProfile = (masterProfile && masterProfile.experience && masterProfile.experience.length > 0)
        ? masterProfile
        : undefined;

      // 1. Post to async endpoint
      const postRes = await fetch(`${BACKEND_API_URL}/tailor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_role: currentJd.jobTitle,
          company_name: currentJd.companyName,
          raw_job_description: currentJd.rawText,
          required_years: 3.0,
          master_profile: effectiveProfile
        })
      });

      if (!postRes.ok) {
        throw new Error(`Server returned ${postRes.status}`);
      }

      const { task_id } = await postRes.json();
      let completed = false;

      // 2. Connect to WebSocket Progress Channel
      const wsUrl = `ws://localhost:8000/ws/v1/tasks/${task_id}`;
      let ws: WebSocket | null = null;
      try {
        ws = new WebSocket(wsUrl);
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.stage) setTailorStage(data.stage);
            if (data.status === 'COMPLETED') {
              completed = true;
              setIsTailoring(false);
              setTailorResult({
                score: data.ats_score,
                pdfBase64: data.pdf_base64
              });
              if (ws) ws.close();
            } else if (data.status === 'FAILED') {
              completed = true;
              setIsTailoring(false);
              alert(`Tailoring failed: ${data.error}`);
              if (ws) ws.close();
            }
          } catch (e) {
            console.warn('[RoleSync UI] Failed to parse WS message:', e);
          }
        };
      } catch (wsErr) {
        console.warn('[RoleSync UI] WebSocket connection failed, relying on HTTP polling:', wsErr);
      }

      // 3. Resilient Polling Fallback
      const interval = setInterval(async () => {
        if (completed) {
          clearInterval(interval);
          return;
        }
        try {
          const pollRes = await fetch(`${BACKEND_API_URL}/tailor/${task_id}`);
          if (pollRes.ok) {
            const data = await pollRes.json();
            if (data.stage) setTailorStage(data.stage);
            if (data.status === 'COMPLETED') {
              completed = true;
              clearInterval(interval);
              setIsTailoring(false);
              setTailorResult({
                score: data.ats_score,
                pdfBase64: data.pdf_base64
              });
              if (ws) ws.close();
            } else if (data.status === 'FAILED') {
              completed = true;
              clearInterval(interval);
              setIsTailoring(false);
              alert(`Tailoring failed: ${data.error}`);
              if (ws) ws.close();
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
      { selector: 'input[name*="name"], #name, input[id*="first_name"]', value: masterProfile?.personal.full_name || 'Alex Mercer', type: 'TEXT' },
      { selector: 'input[name*="email"], #email', value: masterProfile?.personal.email || 'alex@mercer.dev', type: 'TEXT' },
      { selector: 'input[name*="phone"], #phone', value: masterProfile?.personal.phone || '+1 (555) 019-2834', type: 'TEXT' }
    ];

    chrome.tabs.sendMessage(tabs[0].id, {
      action: 'EXECUTE_DOM_AUTOFILL',
      correlationId: `autofill_${Date.now()}`,
      timestamp: Date.now(),
      payload: { mappings: sampleMappings, resumeDataUri: tailorResult?.pdfBase64 }
    } as AppExtensionMessage);
  };

  // Generate CAN-SPAM compliant cold outreach email
  const handleGenerateOutreach = async () => {
    if (!currentJd) return;
    setIsGeneratingOutreach(true);
    try {
      const res = await fetch(`${BACKEND_API_URL}/outreach/synthesize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_name: masterProfile?.personal.full_name || 'Alex Mercer',
          candidate_role: masterProfile?.experience[0]?.role || 'Senior Software Engineer',
          candidate_summary: masterProfile?.summary || 'Senior engineer specializing in cloud systems.',
          recruiter_name: 'Hiring Lead',
          recruiter_email: `recruiting@${currentJd.companyName.toLowerCase().replace(/[^a-z0-9]/g, '')}.com`,
          recruiter_title: 'Engineering Recruiter',
          company_name: currentJd.companyName,
          target_job_title: currentJd.jobTitle,
          mode: 'copilot'
        })
      });

      if (res.ok) {
        const data = await res.json();
        setOutreachDraft(data.draft);
      }
    } catch (e) {
      console.error('[RoleSync UI] Outreach synthesis error:', e);
    } finally {
      setIsGeneratingOutreach(false);
    }
  };

  const handleCopyOutreach = () => {
    if (!outreachDraft) return;
    const textToCopy = `Subject: ${outreachDraft.subject}\n\n${outreachDraft.body_text}\n\n--\n${outreachDraft.physical_address}\nOpt-out: ${outreachDraft.opt_out_link}`;
    navigator.clipboard.writeText(textToCopy);
    setOutreachCopied(true);
    setTimeout(() => setOutreachCopied(false), 3000);
  };

  // Preset demo jobs for fast testing without active tabs
  const handleLoadSampleJd = (type: 'stripe' | 'snowflake') => {
    if (type === 'stripe') {
      setCurrentJd({
        jobTitle: 'Senior Infrastructure Engineer',
        companyName: 'Stripe',
        atsProvider: 'GREENHOUSE',
        rawText: 'We are seeking a Senior Infrastructure Engineer proficient in Python, Docker, Kubernetes, and PostgreSQL with experience scaling cloud microservices and high-throughput transaction pipelines on AWS.',
        cleanedHtml: '<p>Senior Infrastructure Engineer at Stripe. Requirements: Python, Docker, Kubernetes, PostgreSQL, AWS.</p>',
        pageUrl: 'https://boards.greenhouse.io/stripe/jobs/sample'
      });
    } else {
      setCurrentJd({
        jobTitle: 'Staff Backend Systems Engineer',
        companyName: 'Snowflake',
        atsProvider: 'WORKDAY',
        rawText: 'Looking for a Staff Engineer skilled in FastAPI, Python, Redis, distributed systems, and Kubernetes to lead high-concurrency cloud data processing infrastructure.',
        cleanedHtml: '<p>Staff Backend Systems Engineer at Snowflake. Requirements: FastAPI, Python, Redis, Kubernetes.</p>',
        pageUrl: 'https://snowflake.wd1.myworkdayjobs.com/sample'
      });
    }
    setTailorResult(null);
    setOutreachDraft(null);
  };

  const handleSaveManualJd = () => {
    if (!manualTitle.trim() || !manualCompany.trim() || !manualText.trim()) return;
    setCurrentJd({
      jobTitle: manualTitle.trim(),
      companyName: manualCompany.trim(),
      atsProvider: 'GENERIC',
      rawText: manualText.trim(),
      cleanedHtml: `<p>${manualText.trim()}</p>`,
      pageUrl: 'https://careers.direct.com'
    });
    setShowManualJdModal(false);
    setTailorResult(null);
    setOutreachDraft(null);
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
        <div className="flex items-center gap-2">
          <button
            onClick={handleScanCurrentTab}
            disabled={isScanningTab}
            className="px-2 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold text-[11px] rounded-lg border border-indigo-200 transition-colors shadow-xs flex items-center gap-1 disabled:opacity-50"
            title="Scan active browser tab for job requirements"
          >
            <span>{isScanningTab ? '⏳ Scanning...' : '⚡ Scan Tab'}</span>
          </button>
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
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="flex border-b border-slate-200 bg-white px-4 shrink-0">
        <button
          onClick={() => setActiveTab('copilot')}
          className={`py-2.5 px-3 text-xs font-bold border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === 'copilot'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>Copilot & Autofill</span>
          {currentJd && (
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          )}
        </button>
        <button
          onClick={() => setActiveTab('profile')}
          className={`py-2.5 px-3 text-xs font-bold border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === 'profile'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>Master Profile</span>
          <span className="text-[10px] bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded font-semibold border border-indigo-100">
            Vault
          </span>
        </button>
      </nav>

      {/* Main Container */}
      <main className="p-4 flex-1 flex flex-col gap-4">
        {activeTab === 'profile' ? (
          <ProfileEditor
            onSave={(p) => setMasterProfile(p)}
            apiBaseUrl={BACKEND_API_URL}
          />
        ) : currentJd ? (
          <>
            {/* Job Header Card */}
            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-100">
                  {currentJd.atsProvider}
                </span>
                <button
                  onClick={() => setCurrentJd(null)}
                  className="text-xs text-slate-400 hover:text-rose-500 transition-colors"
                  title="Clear Job"
                >
                  ✕ Clear
                </button>
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
                {isTailoring
                  ? (tailorStage ? `Stage: ${tailorStage}...` : 'Verifying Guardrails & Tailoring...')
                  : 'Tailor Resume & Calculate ATS Score'}
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
                  link.download = `RoleSync_${currentJd.companyName.replace(/\s+/g, '_')}_Tailored_Resume.pdf`;
                  link.click();
                }}
              />
            )}

            {/* Recruiter Cold Outreach Card */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Recruiter Cold Outreach
                  </h3>
                  <p className="text-[11px] text-slate-500">CAN-SPAM compliant direct note (&lt;120 words)</p>
                </div>
                <button
                  onClick={handleGenerateOutreach}
                  disabled={isGeneratingOutreach}
                  className="py-1.5 px-3 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold text-xs rounded-lg border border-indigo-200 transition-colors disabled:opacity-50"
                >
                  {isGeneratingOutreach ? 'Synthesizing...' : (outreachDraft ? 'Regenerate' : '✨ Draft Email')}
                </button>
              </div>

              {outreachDraft && (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex flex-col gap-2 text-xs">
                  <div className="flex items-center justify-between border-b border-slate-200 pb-1.5">
                    <span className="font-semibold text-slate-800 text-[11px]">
                      Subject: {outreachDraft.subject}
                    </span>
                    <span className="text-[10px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded font-medium border border-emerald-200">
                      {outreachDraft.word_count} words • Compliant
                    </span>
                  </div>
                  <p className="text-slate-700 leading-relaxed text-[11px] whitespace-pre-line">
                    {outreachDraft.body_text}
                  </p>
                  <div className="pt-2 border-t border-slate-200 flex items-center justify-between gap-2">
                    <span className="text-[10px] text-slate-400">Includes 1-click opt-out</span>
                    <div className="flex items-center gap-1.5">
                      <a
                        href={`https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(outreachDraft.recipient_email || '')}&su=${encodeURIComponent(outreachDraft.subject)}&body=${encodeURIComponent(outreachDraft.body_text + '\n\n--\n' + outreachDraft.physical_address + '\nOpt-out: ' + outreachDraft.opt_out_link)}`}
                        target="_blank"
                        rel="noreferrer"
                        className="py-1 px-2.5 bg-red-600 hover:bg-red-700 text-white font-semibold text-[11px] rounded transition-colors shadow-sm inline-flex items-center gap-1"
                      >
                        ✉️ Open in Gmail
                      </a>
                      <button
                        onClick={handleCopyOutreach}
                        className="py-1 px-2.5 bg-slate-800 hover:bg-slate-900 text-white font-semibold text-[11px] rounded transition-colors shadow-sm"
                      >
                        {outreachCopied ? '✓ Copied!' : 'Copy Text'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

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
          <div className="p-6 bg-white rounded-xl border border-dashed border-slate-300 text-center flex flex-col items-center justify-center gap-4 flex-1">
            <div className="w-12 h-12 rounded-full bg-indigo-50 flex items-center justify-center text-indigo-600 text-xl font-bold">
              🔍
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-800">No Job Detected on Current Page</h3>
              <p className="text-xs text-slate-500 max-w-[260px] leading-relaxed mt-1">
                Open any job posting on Greenhouse, Lever, Workday, LinkedIn, Indeed, or company career sites.
              </p>
            </div>

            {/* ⚡ Scan Active Tab Button */}
            <button
              onClick={handleScanCurrentTab}
              disabled={isScanningTab}
              className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-lg shadow transition-all flex items-center justify-center gap-2 focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              <span>{isScanningTab ? '⏳ Inspecting Active Page...' : '⚡ Scan Active Tab for Job'}</span>
            </button>
            {scanMessage && (
              <span className="text-[11px] font-medium text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-lg border border-indigo-100">
                {scanMessage}
              </span>
            )}

            {/* Test Simulator Buttons */}
            <div className="w-full pt-4 border-t border-slate-100 flex flex-col gap-2">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Or Test Immediately with Demo Jobs
              </span>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <button
                  onClick={() => handleLoadSampleJd('stripe')}
                  className="p-2.5 bg-slate-50 hover:bg-indigo-50 border border-slate-200 hover:border-indigo-200 rounded-lg text-left transition-all group"
                >
                  <div className="font-bold text-slate-800 group-hover:text-indigo-600">Stripe</div>
                  <div className="text-[10px] text-slate-500">Greenhouse • Python, K8s</div>
                </button>
                <button
                  onClick={() => handleLoadSampleJd('snowflake')}
                  className="p-2.5 bg-slate-50 hover:bg-indigo-50 border border-slate-200 hover:border-indigo-200 rounded-lg text-left transition-all group"
                >
                  <div className="font-bold text-slate-800 group-hover:text-indigo-600">Snowflake</div>
                  <div className="text-[10px] text-slate-500">Workday • FastAPI, Redis</div>
                </button>
              </div>

              <button
                onClick={() => setShowManualJdModal(true)}
                className="py-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-semibold"
              >
                + Paste Custom Job Description
              </button>
            </div>
          </div>
        )}

        {/* Manual JD Modal */}
        {showManualJdModal && (
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-xl border border-slate-200 p-4 w-full max-w-sm flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Custom Job Description
                </h3>
                <button
                  onClick={() => setShowManualJdModal(false)}
                  className="text-slate-400 hover:text-slate-600 font-bold text-sm"
                >
                  ✕
                </button>
              </div>
              <input
                type="text"
                placeholder="Job Title (e.g. Senior Backend Engineer)"
                value={manualTitle}
                onChange={(e) => setManualTitle(e.target.value)}
                className="p-2 border border-slate-300 rounded-lg text-xs"
              />
              <input
                type="text"
                placeholder="Company Name (e.g. Uber)"
                value={manualCompany}
                onChange={(e) => setManualCompany(e.target.value)}
                className="p-2 border border-slate-300 rounded-lg text-xs"
              />
              <textarea
                rows={5}
                placeholder="Paste Job Description requirements and qualifications..."
                value={manualText}
                onChange={(e) => setManualText(e.target.value)}
                className="p-2 border border-slate-300 rounded-lg text-xs resize-none"
              />
              <div className="flex gap-2 justify-end pt-2 border-t border-slate-100">
                <button
                  onClick={() => setShowManualJdModal(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 font-semibold"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveManualJd}
                  className="px-4 py-1.5 bg-indigo-600 text-white font-semibold text-xs rounded-lg shadow-sm"
                >
                  Load Job into Copilot
                </button>
              </div>
            </div>
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
