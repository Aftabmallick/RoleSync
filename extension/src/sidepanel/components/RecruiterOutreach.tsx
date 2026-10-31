import React, { useState, useEffect } from 'react';

export interface DetectedPoster {
  fullName: string;
  title: string;
  profileUrl: string;
}

interface RecruiterContact {
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  title: string;
  confidence_score: number;
  verification_status: string;
  linkedin_url?: string;
}

interface PredictedEmail {
  email: string;
  pattern_name: string;
  confidence_score: number;
  verification_status: string;
  is_deliverable: boolean;
}

interface OutreachDraft {
  subject: string;
  body_text: string;
  word_count: number;
  recipient_email: string;
  opt_out_link: string;
  physical_address: string;
  is_compliant: boolean;
  linkedin_connection_note?: string;
  linkedin_inmail_message?: string;
}

interface RecruiterOutreachProps {
  companyName: string;
  jobTitle: string;
  candidateProfile?: any;
  apiBaseUrl?: string;
  detectedPoster?: DetectedPoster;
  onToast?: (type: 'success' | 'error' | 'warning' | 'info', message: string, title?: string) => void;
}

export const RecruiterOutreach: React.FC<RecruiterOutreachProps> = ({
  companyName,
  jobTitle,
  candidateProfile,
  apiBaseUrl = 'http://localhost:8000/api/v1',
  detectedPoster,
  onToast,
}) => {
  const [recruiters, setRecruiters] = useState<RecruiterContact[]>([]);
  const [isDiscovering, setIsDiscovering] = useState<boolean>(false);
  const [showChannels, setShowChannels] = useState<boolean>(false);

  // Form states for selected recruiter
  const [recruiterName, setRecruiterName] = useState<string>('');
  const [recruiterTitle, setRecruiterTitle] = useState<string>('');
  const [recruiterEmail, setRecruiterEmail] = useState<string>('');

  // Email predictions
  const [isPredicting, setIsPredicting] = useState<boolean>(false);
  const [predictedEmails, setPredictedEmails] = useState<PredictedEmail[]>([]);

  // Verification state
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verifyStatus, setVerifyStatus] = useState<{
    status: string;
    confidence: number;
  } | null>(null);

  // Synthesis & Draft states
  const [isSynthesizing, setIsSynthesizing] = useState<boolean>(false);
  const [draft, setDraft] = useState<OutreachDraft | null>(null);
  const [activeFormat, setActiveFormat] = useState<'linkedin_note' | 'linkedin_inmail' | 'email'>('linkedin_note');
  const [editableSubject, setEditableSubject] = useState<string>('');
  const [editableBody, setEditableBody] = useState<string>('');
  const [editableLiNote, setEditableLiNote] = useState<string>('');
  const [editableInmail, setEditableInmail] = useState<string>('');
  const [copiedFormat, setCopiedFormat] = useState<string | null>(null);

  // Auto-fill from detected job poster if available
  useEffect(() => {
    if (detectedPoster?.fullName && !recruiterName) {
      setRecruiterName(detectedPoster.fullName);
      setRecruiterTitle(detectedPoster.title || 'Technical Recruiter');
    }
  }, [detectedPoster]);

  // Clean company name and role
  const cleanCompany = companyName || 'Company';
  const roleKeywords = (jobTitle || 'Engineering')
    .replace(/(Senior|Staff|Principal|Lead|Junior|Associate|\bII\b|\bIII\b|\bIV\b)/gi, '')
    .trim() || 'Software Engineer';

  // 1-Click Search URLs
  const googleXrayRecruiterUrl = `https://www.google.com/search?q=site:linkedin.com/in/+("Technical+Recruiter"+OR+"Talent+Acquisition")+AND+"${encodeURIComponent(
    cleanCompany
  )}"`;

  const linkedinRecruiterUrl = `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(
    `technical recruiter ${cleanCompany}`
  )}`;

  const googleXrayManagerUrl = `https://www.google.com/search?q=site:linkedin.com/in/+("${encodeURIComponent(
    roleKeywords
  )}"+OR+"Engineering+Manager"+OR+"Head+of+Engineering")+AND+"${encodeURIComponent(cleanCompany)}"`;

  // Discover verified company talent channels
  const handleDiscoverRecruiters = async () => {
    setIsDiscovering(true);
    try {
      const res = await fetch(`${apiBaseUrl}/outreach/discover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: companyName,
          role_title: jobTitle,
          department: 'Engineering',
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setRecruiters(data.recruiters || []);
        setShowChannels(true);
        if (onToast) {
          onToast('info', `Found verified company channels for ${companyName}.`, 'Talent Channels');
        }
      }
    } catch (e) {
      console.error('[RoleSync UI] Error discovering channels:', e);
      if (onToast) onToast('error', 'Could not query company channels.', 'Search Error');
    } finally {
      setIsDiscovering(false);
    }
  };

  // Predict email permutations for any recruiter name
  const handlePredictEmails = async () => {
    if (!recruiterName.trim()) {
      if (onToast) onToast('warning', 'Please enter recruiter name first.', 'Name Required');
      return;
    }
    setIsPredicting(true);
    setPredictedEmails([]);
    try {
      const res = await fetch(`${apiBaseUrl}/outreach/predict-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: recruiterName.trim(),
          company_name: companyName,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setPredictedEmails(data.candidates || []);
        if (data.candidates && data.candidates.length > 0) {
          setRecruiterEmail(data.candidates[0].email);
          setVerifyStatus({
            status: data.candidates[0].verification_status,
            confidence: data.candidates[0].confidence_score,
          });
        }
        if (onToast) {
          onToast('success', `Synthesized ${data.candidates?.length || 0} corporate email patterns with MX check.`, 'Email Predicted');
        }
      }
    } catch (e) {
      console.error('[RoleSync UI] Email prediction error:', e);
      if (onToast) onToast('error', 'Failed to predict email patterns.', 'Prediction Error');
    } finally {
      setIsPredicting(false);
    }
  };

  // Verify email deliverability
  const handleVerifyEmail = async () => {
    if (!recruiterEmail) return;
    setIsVerifying(true);
    try {
      const res = await fetch(`${apiBaseUrl}/outreach/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: recruiterEmail }),
      });

      if (res.ok) {
        const data = await res.json();
        setVerifyStatus({
          status: data.status,
          confidence: data.confidence_score,
        });
        if (onToast) {
          onToast(
            data.status === 'valid' ? 'success' : 'warning',
            `Status: ${data.status.toUpperCase()} (${data.confidence_score}% deliverable)`,
            'Deliverability Check'
          );
        }
      }
    } catch (e) {
      console.error('[RoleSync UI] Email verification error:', e);
    } finally {
      setIsVerifying(false);
    }
  };

  // Synthesize outreach drafts
  const handleSynthesizeDraft = async () => {
    setIsSynthesizing(true);
    try {
      const targetEmail =
        recruiterEmail || `recruiting@${companyName.toLowerCase().replace(/[^a-z0-9]/g, '')}.com`;

      const res = await fetch(`${apiBaseUrl}/outreach/synthesize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_name: candidateProfile?.personal?.full_name || 'Alex Mercer',
          candidate_role: candidateProfile?.experience?.[0]?.role || 'Senior Software Engineer',
          candidate_summary: candidateProfile?.summary || '',
          recruiter_name: recruiterName || 'Hiring Lead',
          recruiter_email: targetEmail,
          recruiter_title: recruiterTitle || 'Technical Recruiter',
          company_name: companyName,
          target_job_title: jobTitle,
          mode: 'copilot',
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setDraft(data.draft);
        setEditableSubject(data.draft.subject);
        setEditableBody(data.draft.body_text);
        setEditableLiNote(data.draft.linkedin_connection_note || '');
        setEditableInmail(data.draft.linkedin_inmail_message || '');
        if (onToast) {
          onToast('success', 'Generated LinkedIn connection note, InMail, and email.', 'Outreach Ready');
        }
      } else {
        const errJson = await res.json().catch(() => ({}));
        if (onToast) onToast('error', errJson.detail || 'Could not synthesize outreach note.', 'Error');
      }
    } catch (e) {
      console.error('[RoleSync UI] Outreach synthesis error:', e);
      if (onToast) onToast('error', 'Error connecting to backend for outreach note.', 'Connection Error');
    } finally {
      setIsSynthesizing(false);
    }
  };

  const handleCopyText = (text: string, formatKey: string) => {
    navigator.clipboard.writeText(text);
    setCopiedFormat(formatKey);
    setTimeout(() => setCopiedFormat(null), 2500);
    if (onToast) onToast('success', 'Copied to clipboard!', 'Copied');
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col gap-3.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
            <span>🎯 Recruiter Discovery & Outreach</span>
          </h3>
          <p className="text-[11px] text-slate-500">
            Find the real hiring team, predict direct work emails, or generate &lt;300 char LinkedIn notes
          </p>
        </div>
      </div>

      {/* 1. Detected Job Poster on Page (LinkedIn / ATS DOM Extraction) */}
      {detectedPoster && detectedPoster.fullName && (
        <div className="p-3 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200 rounded-xl flex items-start justify-between gap-3 shadow-2xs">
          <div className="flex items-start gap-2.5">
            <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-xs">
              👤
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-extrabold text-indigo-700 uppercase tracking-wider bg-white px-1.5 py-0.2 rounded border border-indigo-200">
                  ⭐ Job Poster Found on Page
                </span>
              </div>
              <h4 className="text-xs font-bold text-slate-900 mt-0.5">{detectedPoster.fullName}</h4>
              <p className="text-[11px] text-slate-600 font-medium">{detectedPoster.title}</p>
            </div>
          </div>

          <div className="flex flex-col items-end gap-1.5 shrink-0">
            {detectedPoster.profileUrl && (
              <a
                href={detectedPoster.profileUrl}
                target="_blank"
                rel="noreferrer"
                className="px-2 py-1 bg-white hover:bg-slate-50 text-indigo-700 font-semibold text-[11px] rounded-lg border border-indigo-200 transition-colors shadow-2xs inline-flex items-center gap-1"
                title="Open LinkedIn Profile"
              >
                <span>Profile ↗</span>
              </a>
            )}
            <button
              onClick={() => {
                setRecruiterName(detectedPoster.fullName);
                setRecruiterTitle(detectedPoster.title || 'Technical Recruiter');
                handlePredictEmails();
              }}
              className="px-2 py-1 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-[11px] rounded-lg transition-colors shadow-2xs"
            >
              Reach Out
            </button>
          </div>
        </div>
      )}

      {/* 2. 1-Click Targeted Deep Searches (Industry Standard Approach) */}
      <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold text-slate-700 uppercase tracking-wider">
            1-Click Live Recruiter Searches ({cleanCompany}):
          </span>
          <span className="text-[10px] text-slate-400">Direct query in your browser</span>
        </div>

        <div className="grid grid-cols-3 gap-1.5 text-xs">
          <a
            href={googleXrayRecruiterUrl}
            target="_blank"
            rel="noreferrer"
            className="p-2 bg-white hover:bg-indigo-50 border border-slate-200 hover:border-indigo-300 rounded-lg transition-all shadow-2xs text-center flex flex-col items-center justify-center gap-0.5 group"
            title="Search Google's public index of LinkedIn profiles for recruiters at this company"
          >
            <span className="font-bold text-slate-800 group-hover:text-indigo-600 text-[11px]">
              🔍 Google X-Ray
            </span>
            <span className="text-[10px] text-slate-500">Recruiters on LinkedIn</span>
          </a>

          <a
            href={linkedinRecruiterUrl}
            target="_blank"
            rel="noreferrer"
            className="p-2 bg-white hover:bg-indigo-50 border border-slate-200 hover:border-indigo-300 rounded-lg transition-all shadow-2xs text-center flex flex-col items-center justify-center gap-0.5 group"
            title="Search LinkedIn People directory for talent acquisition team members"
          >
            <span className="font-bold text-slate-800 group-hover:text-indigo-600 text-[11px]">
              💼 LinkedIn People
            </span>
            <span className="text-[10px] text-slate-500">Active Talent Team</span>
          </a>

          <a
            href={googleXrayManagerUrl}
            target="_blank"
            rel="noreferrer"
            className="p-2 bg-white hover:bg-indigo-50 border border-slate-200 hover:border-indigo-300 rounded-lg transition-all shadow-2xs text-center flex flex-col items-center justify-center gap-0.5 group"
            title="Search for the Engineering Manager or Director leading this department"
          >
            <span className="font-bold text-slate-800 group-hover:text-indigo-600 text-[11px]">
              👔 Hiring Lead
            </span>
            <span className="text-[10px] text-slate-500">Eng Managers / Leads</span>
          </a>
        </div>
      </div>

      {/* 3. Recruiter Name & Email Predictor */}
      <div className="p-3 bg-white border border-slate-200 rounded-xl flex flex-col gap-2.5 shadow-2xs">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold text-slate-800 uppercase tracking-wider">
            Target Recruiter / Contact:
          </span>
          <button
            onClick={handleDiscoverRecruiters}
            disabled={isDiscovering}
            className="text-[11px] text-indigo-600 hover:text-indigo-800 font-semibold cursor-pointer"
          >
            {isDiscovering ? 'Searching...' : showChannels ? 'Hide Company Inboxes' : 'View Company Inboxes ▾'}
          </button>
        </div>

        {/* Company Channels list toggle */}
        {showChannels && recruiters.length > 0 && (
          <div className="p-2 bg-slate-50 rounded-lg border border-slate-200 flex flex-col gap-1.5">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              Verified Company Talent Inboxes:
            </span>
            {recruiters.map((rec, i) => (
              <div
                key={i}
                onClick={() => {
                  setRecruiterName(rec.full_name);
                  setRecruiterTitle(rec.title);
                  setRecruiterEmail(rec.email);
                  setVerifyStatus({ status: rec.verification_status, confidence: rec.confidence_score });
                }}
                className="p-1.5 bg-white hover:bg-indigo-50 rounded border border-slate-200 cursor-pointer flex items-center justify-between text-xs transition-colors"
              >
                <div>
                  <span className="font-bold text-slate-800 text-[11px]">{rec.full_name}</span>
                  <span className="text-[10px] text-slate-500 block">{rec.title}</span>
                </div>
                <span className="font-mono text-[10px] text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-100">
                  {rec.email}
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-[10px] font-bold text-slate-500 uppercase mb-0.5">Recruiter Full Name</label>
            <input
              type="text"
              placeholder="e.g. Sarah Chen"
              value={recruiterName}
              onChange={(e) => setRecruiterName(e.target.value)}
              className="w-full p-2 border border-slate-200 rounded-lg text-xs bg-slate-50 focus:bg-white focus:ring-1 focus:ring-indigo-500 font-medium"
            />
          </div>
          <div>
            <label className="block text-[10px] font-bold text-slate-500 uppercase mb-0.5">Title / Role</label>
            <input
              type="text"
              placeholder="e.g. Senior Tech Recruiter"
              value={recruiterTitle}
              onChange={(e) => setRecruiterTitle(e.target.value)}
              className="w-full p-2 border border-slate-200 rounded-lg text-xs bg-slate-50 focus:bg-white focus:ring-1 focus:ring-indigo-500 font-medium"
            />
          </div>
        </div>

        {/* Email prediction trigger & input */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label className="text-[10px] font-bold text-slate-500 uppercase">Work Email</label>
            <button
              onClick={handlePredictEmails}
              disabled={isPredicting || !recruiterName.trim()}
              className="text-[10px] font-bold text-indigo-600 hover:text-indigo-800 disabled:opacity-40 cursor-pointer flex items-center gap-1"
            >
              <span>{isPredicting ? '⏳ Predicting Patterns...' : '⚡ Predict Work Emails (DNS Check)'}</span>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="email"
              placeholder="e.g. sarah.chen@company.com"
              value={recruiterEmail}
              onChange={(e) => setRecruiterEmail(e.target.value)}
              className="flex-1 p-2 border border-slate-200 rounded-lg text-xs font-mono bg-slate-50 focus:bg-white focus:ring-1 focus:ring-indigo-500"
            />
            <button
              onClick={handleVerifyEmail}
              disabled={isVerifying || !recruiterEmail}
              className="px-2.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-lg border border-slate-200 transition-colors disabled:opacity-40"
            >
              {isVerifying ? 'Checking...' : 'Verify'}
            </button>
          </div>

          {verifyStatus && (
            <div className="flex items-center justify-between text-[11px] px-1">
              <span className="flex items-center gap-1 font-semibold text-emerald-700">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                MX Deliverability: {verifyStatus.status.toUpperCase()} ({verifyStatus.confidence}%)
              </span>
              <span className="text-[10px] text-slate-400">DNS Verified</span>
            </div>
          )}

          {/* Predicted emails selection pills */}
          {predictedEmails.length > 0 && (
            <div className="p-2 bg-indigo-50/60 rounded-lg border border-indigo-100 flex flex-col gap-1.5 mt-1">
              <span className="text-[10px] font-bold text-indigo-900 uppercase tracking-wider">
                Predicted Email Permutations (Click to select):
              </span>
              <div className="grid grid-cols-1 gap-1">
                {predictedEmails.map((opt, idx) => (
                  <div
                    key={idx}
                    onClick={() => {
                      setRecruiterEmail(opt.email);
                      setVerifyStatus({ status: opt.verification_status, confidence: opt.confidence_score });
                    }}
                    className={`p-1.5 rounded border text-xs cursor-pointer flex items-center justify-between transition-colors ${
                      recruiterEmail === opt.email
                        ? 'bg-indigo-600 text-white border-indigo-700'
                        : 'bg-white hover:bg-indigo-50 text-slate-800 border-indigo-200'
                    }`}
                  >
                    <span className="font-mono text-[11px]">{opt.email}</span>
                    <span className="text-[10px] font-medium opacity-80">{opt.pattern_name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Generate Button */}
        <button
          onClick={handleSynthesizeDraft}
          disabled={isSynthesizing}
          className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-lg shadow-xs transition-colors disabled:opacity-50 mt-1 flex items-center justify-center gap-1.5"
        >
          <span>{isSynthesizing ? '⏳ Drafting Outreach Messages...' : '✨ Generate Outreach Notes (3 Formats)'}</span>
        </button>
      </div>

      {/* 4. Multi-Format Outreach Output */}
      {draft && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 flex flex-col gap-3 shadow-2xs">
          {/* Format Selector Tabs */}
          <div className="flex bg-white p-0.5 rounded-lg border border-slate-200 text-xs font-bold">
            <button
              onClick={() => setActiveFormat('linkedin_note')}
              className={`flex-1 py-1.5 px-2 rounded-md transition-all text-center flex items-center justify-center gap-1 ${
                activeFormat === 'linkedin_note'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <span>🔗 LinkedIn Invite</span>
              <span className="text-[10px] px-1 rounded bg-black/10">&lt;300 chars</span>
            </button>
            <button
              onClick={() => setActiveFormat('linkedin_inmail')}
              className={`flex-1 py-1.5 px-2 rounded-md transition-all text-center ${
                activeFormat === 'linkedin_inmail'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              💬 LinkedIn InMail
            </button>
            <button
              onClick={() => setActiveFormat('email')}
              className={`flex-1 py-1.5 px-2 rounded-md transition-all text-center ${
                activeFormat === 'email'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              ✉️ Direct Email
            </button>
          </div>

          {/* Active Format 1: LinkedIn Connection Note (<300 chars) */}
          {activeFormat === 'linkedin_note' && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-700">LinkedIn Connection Note:</span>
                <span
                  className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                    editableLiNote.length <= 300
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-rose-50 text-rose-700 border border-rose-200'
                  }`}
                >
                  {editableLiNote.length} / 300 characters
                </span>
              </div>
              <textarea
                rows={4}
                value={editableLiNote}
                onChange={(e) => setEditableLiNote(e.target.value)}
                className="w-full p-2.5 border border-slate-200 rounded-lg text-xs text-slate-800 bg-white focus:ring-1 focus:ring-indigo-500 font-medium resize-none leading-relaxed"
                placeholder="Short note to accompany LinkedIn connection invitation..."
              />
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => handleCopyText(editableLiNote, 'li_note')}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs rounded-lg shadow-xs transition-colors"
                >
                  {copiedFormat === 'li_note' ? '✓ Copied Invite Note!' : 'Copy Connection Note'}
                </button>
              </div>
            </div>
          )}

          {/* Active Format 2: LinkedIn InMail / Message */}
          {activeFormat === 'linkedin_inmail' && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-700">LinkedIn Direct Message / InMail:</span>
                <span className="text-[10px] text-slate-500">
                  {editableInmail.split(/\s+/).filter(Boolean).length} words
                </span>
              </div>
              <textarea
                rows={6}
                value={editableInmail}
                onChange={(e) => setEditableInmail(e.target.value)}
                className="w-full p-2.5 border border-slate-200 rounded-lg text-xs text-slate-800 bg-white focus:ring-1 focus:ring-indigo-500 font-medium resize-y leading-relaxed"
              />
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => handleCopyText(editableInmail, 'li_inmail')}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs rounded-lg shadow-xs transition-colors"
                >
                  {copiedFormat === 'li_inmail' ? '✓ Copied InMail!' : 'Copy InMail'}
                </button>
              </div>
            </div>
          )}

          {/* Active Format 3: Direct Email (CAN-SPAM Compliant) */}
          {activeFormat === 'email' && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-700">Subject:</span>
                <span className="text-[10px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded font-semibold border border-emerald-200">
                  {editableBody.split(/\s+/).filter(Boolean).length} words • CAN-SPAM Compliant
                </span>
              </div>
              <input
                type="text"
                value={editableSubject}
                onChange={(e) => setEditableSubject(e.target.value)}
                className="w-full p-2 border border-slate-200 rounded-lg text-xs font-semibold text-slate-800 bg-white"
              />
              <textarea
                rows={6}
                value={editableBody}
                onChange={(e) => setEditableBody(e.target.value)}
                className="w-full p-2.5 border border-slate-200 rounded-lg text-xs text-slate-700 font-mono resize-y bg-white leading-relaxed"
              />

              <div className="flex items-center justify-between gap-2 pt-1">
                <span className="text-[10px] text-slate-400">Includes 1-click opt-out & address</span>
                <div className="flex items-center gap-1.5">
                  <a
                    href={`https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(
                      recruiterEmail || draft.recipient_email || ''
                    )}&su=${encodeURIComponent(editableSubject)}&body=${encodeURIComponent(
                      editableBody + '\n\n--\n' + draft.physical_address + '\nOpt-out: ' + draft.opt_out_link
                    )}`}
                    target="_blank"
                    rel="noreferrer"
                    className="py-1.5 px-3 bg-red-600 hover:bg-red-700 text-white font-semibold text-xs rounded-lg transition-colors shadow-xs inline-flex items-center gap-1"
                  >
                    ✉️ Open in Gmail
                  </a>
                  <button
                    onClick={() => handleCopyText(`Subject: ${editableSubject}\n\n${editableBody}`, 'email')}
                    className="py-1.5 px-3 bg-slate-800 hover:bg-slate-900 text-white font-semibold text-xs rounded-lg transition-colors shadow-xs"
                  >
                    {copiedFormat === 'email' ? '✓ Copied!' : 'Copy Email'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
