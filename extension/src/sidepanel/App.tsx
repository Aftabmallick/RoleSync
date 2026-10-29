import { useEffect, useState } from 'react';
import { KeepaliveManager } from '../background/KeepaliveManager';
import { JDExtractedPayload, AppExtensionMessage } from '../types/messages';
import { ScoreCard, ScoreBreakdown } from './components/ScoreCard';
import { PdfPreview } from './components/PdfPreview';
import { AutofillProgress } from './components/AutofillProgress';
import { ProfileEditor, MasterProfileData } from './components/ProfileEditor';
import { TailorDiffViewer } from './components/TailorDiffViewer';
import { CoverLetterViewer } from './components/CoverLetterViewer';
import { RecruiterOutreach } from './components/RecruiterOutreach';
import { ApplicationsTracker } from './components/ApplicationsTracker';
import { ResumeMatcher, ResumeVersion } from './components/ResumeMatcher';

const BACKEND_API_URL = 'http://localhost:8000/api/v1';

export default function App() {
  const [activeTab, setActiveTab] = useState<'copilot' | 'applications' | 'profile'>('copilot');
  const [executionMode, setExecutionMode] = useState<'copilot' | 'autopilot'>('copilot');
  const [masterProfile, setMasterProfile] = useState<MasterProfileData | null>(null);
  const [keepaliveConnected, setKeepaliveConnected] = useState<boolean>(false);
  const [currentJd, setCurrentJd] = useState<JDExtractedPayload | null>(null);
  const [isTailoring, setIsTailoring] = useState<boolean>(false);
  const [tailorStage, setTailorStage] = useState<string>('');
  const [tailorResult, setTailorResult] = useState<{
    score?: ScoreBreakdown;
    pdfBase64?: string;
    tailored_draft?: any;
  } | null>(null);

  // Autofill & Autopilot progress states
  const [autofillProgress, setAutofillProgress] = useState<{
    completed: number;
    total: number;
    current: string;
  } | null>(null);

  const [isAutopilotRunning, setIsAutopilotRunning] = useState<boolean>(false);
  const [autopilotState, setAutopilotState] = useState<{
    stage: string;
    completed: number;
    failed: number;
    isPausedForReview?: boolean;
    message?: string;
  } | null>(null);

  // Tracker quick-save state
  const [appSavedMessage, setAppSavedMessage] = useState<string | null>(null);
  const [jobToTrack, setJobToTrack] = useState<{
    companyName: string;
    jobTitle: string;
    atsProvider?: string;
    pageUrl?: string;
    score?: number;
  } | null>(null);

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

      chrome.tabs.sendMessage(activeTab.id, { action: 'TRIGGER_PAGE_EXTRACTION' }, async (response) => {
        if (chrome.runtime.lastError || !response) {
          try {
            await chrome.scripting.executeScript({
              target: { tabId: activeTab.id! },
              files: ['dist/content/injector.js'],
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

        // Listen for progress messages
        const messageListener = (msg: any) => {
          if (msg.action === 'AUTOFILL_PROGRESS') {
            setAutofillProgress({
              completed: msg.payload.fieldsCompleted,
              total: msg.payload.totalFields,
              current: msg.payload.currentFieldSelector,
            });
          }
          if (msg.action === 'AUTOPILOT_PROGRESS') {
            setAutopilotState({
              stage: msg.payload.stage,
              completed: msg.payload.fieldsCompleted,
              failed: msg.payload.fieldsFailed,
              isPausedForReview: msg.payload.isPausedForReview,
              message: msg.payload.message,
            });
            setIsAutopilotRunning(false);
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
    setAppSavedMessage(null);

    try {
      const effectiveProfile =
        masterProfile && masterProfile.experience && masterProfile.experience.length > 0
          ? masterProfile
          : undefined;

      const postRes = await fetch(`${BACKEND_API_URL}/tailor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_role: currentJd.jobTitle,
          company_name: currentJd.companyName,
          raw_job_description: currentJd.rawText,
          required_years: 3.0,
          master_profile: effectiveProfile,
        }),
      });

      if (!postRes.ok) {
        throw new Error(`Server returned ${postRes.status}`);
      }

      const { task_id } = await postRes.json();
      let completed = false;

      // Connect to WebSocket Progress Channel
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
                pdfBase64: data.pdf_base64,
                tailored_draft: data.tailored_draft,
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

      // Resilient Polling Fallback
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
                pdfBase64: data.pdf_base64,
                tailored_draft: data.tailored_draft,
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

  // Copilot Mode 1-Click Autofill
  const handleExecuteAutofill = async () => {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs[0]?.id) return;

    setAutofillProgress({ completed: 0, total: 6, current: 'Initializing...' });

    chrome.tabs.sendMessage(tabs[0].id, {
      action: 'EXECUTE_DOM_AUTOFILL',
      correlationId: `autofill_${Date.now()}`,
      timestamp: Date.now(),
      payload: {
        candidateProfile: masterProfile,
        resumeDataUri: tailorResult?.pdfBase64,
      },
    } as AppExtensionMessage);
  };

  // Autopilot Mode Supervised Traversal
  const handleExecuteAutopilot = async () => {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs[0]?.id) return;

    setIsAutopilotRunning(true);
    setAutopilotState({
      stage: 'DETECTING_STAGE',
      completed: 0,
      failed: 0,
      message: 'Inspecting wizard DOM stage and preparing inputs...',
    });

    chrome.tabs.sendMessage(tabs[0].id, {
      action: 'EXECUTE_AUTOPILOT',
      correlationId: `autopilot_${Date.now()}`,
      timestamp: Date.now(),
      payload: {
        candidateProfile: masterProfile,
        resumeDataUri: tailorResult?.pdfBase64,
        autoAdvance: true,
      },
    } as AppExtensionMessage);
  };

  // Quick Save Job to Application Tracker
  const handleSaveToTracker = () => {
    if (!currentJd) return;
    setJobToTrack({
      companyName: currentJd.companyName,
      jobTitle: currentJd.jobTitle,
      atsProvider: currentJd.atsProvider,
      pageUrl: currentJd.pageUrl,
      score: tailorResult?.score?.composite_score || 85,
    });
    setAppSavedMessage('✓ Application saved to tracker pipeline!');
    setTimeout(() => setAppSavedMessage(null), 3500);
  };

  const handleVersionSelected = (
    version: ResumeVersion | null,
    profileData: any,
    pdfBase64?: string,
    score?: ScoreBreakdown
  ) => {
    if (score && pdfBase64) {
      setTailorResult({
        score,
        pdfBase64,
        tailored_draft: {
          experience: profileData?.experience || masterProfile?.experience,
        },
      });
    } else if (pdfBase64) {
      const fallbackScore: ScoreBreakdown = {
        composite_score: version?.ats_score || 85,
        semantic_score: 82,
        skill_coverage_score: 88,
        lexical_score: 84,
        experience_alignment_score: 85,
      };
      setTailorResult((prev) => ({
        score: prev?.score || fallbackScore,
        pdfBase64,
        tailored_draft: {
          experience: profileData?.experience || masterProfile?.experience,
        },
      }));
    }
  };

  const handleNewProfileUploaded = (newProfile: MasterProfileData) => {
    setMasterProfile(newProfile);
    if (typeof chrome !== 'undefined' && chrome.storage?.local) {
      chrome.storage.local.set({ rolesync_master_profile: newProfile });
    }
  };

  // Preset demo jobs for fast testing
  const handleLoadSampleJd = (type: 'stripe' | 'snowflake') => {
    if (type === 'stripe') {
      setCurrentJd({
        jobTitle: 'Senior Infrastructure Engineer',
        companyName: 'Stripe',
        atsProvider: 'GREENHOUSE',
        rawText:
          'We are seeking a Senior Infrastructure Engineer proficient in Python, Docker, Kubernetes, and PostgreSQL with experience scaling cloud microservices and high-throughput transaction pipelines on AWS.',
        cleanedHtml:
          '<p>Senior Infrastructure Engineer at Stripe. Requirements: Python, Docker, Kubernetes, PostgreSQL, AWS.</p>',
        pageUrl: 'https://boards.greenhouse.io/stripe/jobs/sample',
      });
    } else {
      setCurrentJd({
        jobTitle: 'Staff Backend Systems Engineer',
        companyName: 'Snowflake',
        atsProvider: 'WORKDAY',
        rawText:
          'Looking for a Staff Engineer skilled in FastAPI, Python, Redis, distributed systems, and Kubernetes to lead high-concurrency cloud data processing infrastructure.',
        cleanedHtml:
          '<p>Staff Backend Systems Engineer at Snowflake. Requirements: FastAPI, Python, Redis, Kubernetes.</p>',
        pageUrl: 'https://snowflake.wd1.myworkdayjobs.com/sample',
      });
    }
    setTailorResult(null);
  };

  const handleSaveManualJd = () => {
    if (!manualTitle.trim() || !manualCompany.trim() || !manualText.trim()) return;
    setCurrentJd({
      jobTitle: manualTitle.trim(),
      companyName: manualCompany.trim(),
      atsProvider: 'GENERIC',
      rawText: manualText.trim(),
      cleanedHtml: `<p>${manualText.trim()}</p>`,
      pageUrl: 'https://careers.direct.com',
    });
    setShowManualJdModal(false);
    setTailorResult(null);
  };

  return (
    <div className="flex flex-col min-h-screen bg-slate-50 text-slate-800 font-sans">
      {/* Header */}
      <header className="p-3.5 border-b border-slate-200 bg-white flex items-center justify-between shadow-xs sticky top-0 z-20">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm shadow-sm">
            RS
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-900 leading-tight">RoleSync Copilot</h1>
            <p className="text-[11px] text-slate-500">Autonomous ATS Orchestrator v2.0</p>
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
      <nav className="flex border-b border-slate-200 bg-white px-3 shrink-0">
        <button
          onClick={() => setActiveTab('copilot')}
          className={`py-2.5 px-3 text-xs font-bold border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === 'copilot'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>Copilot & Autofill</span>
          {currentJd && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />}
        </button>

        <button
          onClick={() => setActiveTab('applications')}
          className={`py-2.5 px-3 text-xs font-bold border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === 'applications'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>Applications</span>
          <span className="text-[10px] bg-purple-50 text-purple-700 px-1.5 py-0.2 rounded font-semibold border border-purple-100">
            Tracker
          </span>
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
          <span className="text-[10px] bg-indigo-50 text-indigo-600 px-1.5 py-0.2 rounded font-semibold border border-indigo-100">
            Vault
          </span>
        </button>
      </nav>

      {/* Main Container */}
      <main className="p-4 flex-1 flex flex-col gap-4">
        {activeTab === 'profile' ? (
          <ProfileEditor onSave={(p) => setMasterProfile(p)} apiBaseUrl={BACKEND_API_URL} />
        ) : activeTab === 'applications' ? (
          <ApplicationsTracker
            apiBaseUrl={BACKEND_API_URL}
            currentJdToSave={jobToTrack}
            onApplicationSaved={() => setJobToTrack(null)}
          />
        ) : currentJd ? (
          <>
            {/* Mode Selector Strip */}
            <div className="bg-white p-2 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                Execution Mode:
              </span>
              <div className="flex bg-slate-100 p-0.5 rounded-lg text-xs font-bold">
                <button
                  onClick={() => setExecutionMode('copilot')}
                  className={`px-3 py-1 rounded-md transition-all ${
                    executionMode === 'copilot'
                      ? 'bg-white text-indigo-600 shadow-xs'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  Copilot (Manual)
                </button>
                <button
                  onClick={() => setExecutionMode('autopilot')}
                  className={`px-3 py-1 rounded-md transition-all flex items-center gap-1 ${
                    executionMode === 'autopilot'
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <span>🚀 Autopilot (Workday)</span>
                </button>
              </div>
            </div>

            {/* Job Header Card */}
            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-100">
                  {currentJd.atsProvider}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSaveToTracker}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold"
                    title="Track in application pipeline"
                  >
                    + Save to Tracker
                  </button>
                  <button
                    onClick={() => setCurrentJd(null)}
                    className="text-xs text-slate-400 hover:text-rose-500 transition-colors"
                    title="Clear Job"
                  >
                    ✕ Clear
                  </button>
                </div>
              </div>

              <h2 className="text-base font-bold text-slate-900">{currentJd.jobTitle}</h2>
              <p className="text-sm text-slate-600 font-medium">{currentJd.companyName}</p>

              {appSavedMessage && (
                <div className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1.5 rounded-lg border border-emerald-200">
                  {appSavedMessage}
                </div>
              )}
            </div>

            {/* Resume Matcher & Score Optimizer */}
            <ResumeMatcher
              currentJd={currentJd}
              baseProfile={masterProfile}
              apiBaseUrl={BACKEND_API_URL}
              onVersionSelected={handleVersionSelected}
              onNewProfileUploaded={handleNewProfileUploaded}
            />

            {/* Optional Deep AI Tailor Card */}
            <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-2xs flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-slate-800">Deep AI Tailoring</span>
                <p className="text-[11px] text-slate-500">Run multi-stage LLM rewrite of all experience bullets</p>
              </div>
              <button
                className={`py-1.5 px-3 font-semibold text-xs rounded-lg shadow-xs transition-all ${
                  isTailoring
                    ? 'bg-indigo-400 cursor-not-allowed text-white'
                    : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                }`}
                disabled={isTailoring}
                onClick={handleTriggerTailoring}
              >
                {isTailoring
                  ? tailorStage
                    ? `${tailorStage}...`
                    : 'Tailoring...'
                  : 'Run Deep Tailor'}
              </button>
            </div>

            {/* ATS Score Card */}
            {tailorResult?.score && <ScoreCard score={tailorResult.score} />}

            {/* Diff Viewer: What changed between master profile and tailored bullets */}
            {tailorResult?.tailored_draft?.experience && (
              <TailorDiffViewer
                tailoredExperience={tailorResult.tailored_draft.experience}
                masterExperience={masterProfile?.experience}
              />
            )}

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

            {/* Cover Letter Generator Card */}
            <CoverLetterViewer
              targetRole={currentJd.jobTitle}
              companyName={currentJd.companyName}
              rawJd={currentJd.rawText}
              candidateProfile={masterProfile}
              apiBaseUrl={BACKEND_API_URL}
            />

            {/* Recruiter Outreach Card with discovery & verification */}
            <RecruiterOutreach
              companyName={currentJd.companyName}
              jobTitle={currentJd.jobTitle}
              candidateProfile={masterProfile}
              apiBaseUrl={BACKEND_API_URL}
            />

            {/* Autofill / Autopilot Action Block */}
            {tailorResult && (
              <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col gap-3">
                {executionMode === 'copilot' ? (
                  <>
                    <button
                      className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm rounded-lg shadow-sm transition-all focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 flex items-center justify-center gap-1.5"
                      onClick={handleExecuteAutofill}
                    >
                      <span>⚡ Execute 1-Click Autofill & Attach Resume</span>
                    </button>
                    {autofillProgress && (
                      <AutofillProgress
                        completed={autofillProgress.completed}
                        total={autofillProgress.total}
                        currentSelector={autofillProgress.current}
                      />
                    )}
                  </>
                ) : (
                  <>
                    <div className="p-3 bg-indigo-50 border border-indigo-100 rounded-lg flex flex-col gap-1 text-xs">
                      <span className="font-bold text-indigo-900">
                        Workday Multi-Stage Autopilot Active
                      </span>
                      <p className="text-[11px] text-indigo-700">
                        Automatically traverses My Information → My Experience → Questions → Disclosures.
                        Always pauses at Review for your final consent.
                      </p>
                    </div>

                    <button
                      className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-lg shadow-sm transition-all focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 flex items-center justify-center gap-1.5 disabled:opacity-50"
                      disabled={isAutopilotRunning}
                      onClick={handleExecuteAutopilot}
                    >
                      <span>
                        {isAutopilotRunning
                          ? '⏳ Running Multi-Step Traversal...'
                          : '🚀 Run Autopilot Traversal'}
                      </span>
                    </button>

                    {autopilotState && (
                      <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg flex flex-col gap-1 text-xs">
                        <div className="flex items-center justify-between font-bold text-slate-800">
                          <span>Stage: {autopilotState.stage}</span>
                          <span className="text-emerald-700">
                            {autopilotState.completed} fields filled
                          </span>
                        </div>
                        {autopilotState.message && (
                          <p className="text-[11px] text-slate-600 leading-relaxed">
                            {autopilotState.message}
                          </p>
                        )}
                        {autopilotState.isPausedForReview && (
                          <div className="mt-1 p-2 bg-amber-50 border border-amber-200 rounded text-amber-800 font-semibold text-[11px]">
                            ⚠️ Paused at Final Review. Inspect responses on page and click Submit.
                          </div>
                        )}
                      </div>
                    )}
                  </>
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

            {/* Scan Active Tab Button */}
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
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
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
