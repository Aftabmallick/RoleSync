import React, { useState } from 'react';

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

interface OutreachDraft {
  subject: string;
  body_text: string;
  word_count: number;
  recipient_email: string;
  opt_out_link: string;
  physical_address: string;
  is_compliant: boolean;
}

interface RecruiterOutreachProps {
  companyName: string;
  jobTitle: string;
  candidateProfile?: any;
  apiBaseUrl?: string;
}

export const RecruiterOutreach: React.FC<RecruiterOutreachProps> = ({
  companyName,
  jobTitle,
  candidateProfile,
  apiBaseUrl = 'http://localhost:8000/api/v1',
}) => {
  const [recruiters, setRecruiters] = useState<RecruiterContact[]>([]);
  const [isDiscovering, setIsDiscovering] = useState<boolean>(false);

  // Form states for selected recruiter
  const [recruiterName, setRecruiterName] = useState<string>('');
  const [recruiterTitle, setRecruiterTitle] = useState<string>('');
  const [recruiterEmail, setRecruiterEmail] = useState<string>('');

  // Email verification state
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verifyStatus, setVerifyStatus] = useState<{
    status: string;
    confidence: number;
  } | null>(null);

  // Synthesis & Draft states
  const [isSynthesizing, setIsSynthesizing] = useState<boolean>(false);
  const [draft, setDraft] = useState<OutreachDraft | null>(null);
  const [editableSubject, setEditableSubject] = useState<string>('');
  const [editableBody, setEditableBody] = useState<string>('');
  const [copied, setCopied] = useState<boolean>(false);

  // Discover recruiters from company domain
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

        // Select the first recruiter by default
        if (data.recruiters && data.recruiters.length > 0) {
          selectRecruiter(data.recruiters[0]);
        }
      }
    } catch (e) {
      console.error('[RoleSync UI] Error discovering recruiters:', e);
    } finally {
      setIsDiscovering(false);
    }
  };

  const selectRecruiter = (rec: RecruiterContact) => {
    setRecruiterName(rec.full_name);
    setRecruiterTitle(rec.title);
    setRecruiterEmail(rec.email);
    setVerifyStatus({
      status: rec.verification_status,
      confidence: rec.confidence_score,
    });
    setDraft(null);
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
      }
    } catch (e) {
      console.error('[RoleSync UI] Email verification error:', e);
    } finally {
      setIsVerifying(false);
    }
  };

  // Synthesize outreach draft
  const handleSynthesizeDraft = async () => {
    setIsSynthesizing(true);
    try {
      const res = await fetch(`${apiBaseUrl}/outreach/synthesize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_name: candidateProfile?.personal?.full_name || 'Alex Mercer',
          candidate_role: candidateProfile?.experience?.[0]?.role || 'Senior Software Engineer',
          candidate_summary: candidateProfile?.summary || '',
          recruiter_name: recruiterName || 'Hiring Lead',
          recruiter_email: recruiterEmail || `recruiting@${companyName.toLowerCase().replace(/[^a-z0-9]/g, '')}.com`,
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
      }
    } catch (e) {
      console.error('[RoleSync UI] Outreach synthesis error:', e);
    } finally {
      setIsSynthesizing(false);
    }
  };

  const handleCopy = () => {
    if (!draft) return;
    const textToCopy = `Subject: ${editableSubject}\n\n${editableBody}\n\n--\n${draft.physical_address}\nOpt-out: ${draft.opt_out_link}`;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col gap-3.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Recruiter Outreach & Hiring Team
          </h3>
          <p className="text-[11px] text-slate-500">
            Find technical recruiters, verify deliverability, and send CAN-SPAM compliant notes (&lt;120 words)
          </p>
        </div>

        <button
          onClick={handleDiscoverRecruiters}
          disabled={isDiscovering}
          className="py-1.5 px-3 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold text-xs rounded-lg border border-indigo-200 transition-colors disabled:opacity-50 flex items-center gap-1"
        >
          <span>{isDiscovering ? 'Searching...' : '🔍 Find Hiring Team'}</span>
        </button>
      </div>

      {/* Recruiter list results */}
      {recruiters.length > 0 && (
        <div className="flex flex-col gap-1.5 p-2 bg-slate-50 rounded-lg border border-slate-200">
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              Discovered at {companyName}:
            </span>
            <a
              href={`https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(`recruiter ${companyName}`)}`}
              target="_blank"
              rel="noreferrer"
              className="text-[10px] text-indigo-600 hover:text-indigo-800 font-semibold"
            >
              Search All on LinkedIn ↗
            </a>
          </div>
          <div className="grid grid-cols-1 gap-1.5">
            {recruiters.map((rec, i) => {
              const isSelected = rec.email === recruiterEmail;
              return (
                <div
                  key={i}
                  onClick={() => selectRecruiter(rec)}
                  className={`p-2 rounded-lg border cursor-pointer transition-all flex items-center justify-between ${
                    isSelected
                      ? 'bg-indigo-50/80 border-indigo-300 ring-1 ring-indigo-200'
                      : 'bg-white border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <div className="flex flex-col">
                    <span className="font-bold text-slate-900 text-xs">{rec.full_name}</span>
                    <span className="text-[10px] text-slate-500">{rec.title}</span>
                    <span className="text-[10px] text-indigo-600 font-mono">{rec.email}</span>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className="text-[9px] font-semibold bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded border border-emerald-200">
                      ✓ {rec.confidence_score}% Match
                    </span>
                    {rec.linkedin_url && (
                      <a
                        href={rec.linkedin_url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-[9px] font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50/80 px-2 py-0.5 rounded border border-indigo-200"
                        title={`Live LinkedIn people search for ${rec.title}`}
                      >
                        LinkedIn Search ↗
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="text-[10px] text-slate-500 bg-white/70 p-1.5 rounded border border-slate-200 flex items-center gap-1">
            <span>💡</span>
            <span>Click <b>LinkedIn Search ↗</b> to pick an active recruiter, or send directly to the verified team email.</span>
          </div>
        </div>
      )}

      {/* Selected Recruiter Editor & Verification */}
      <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
            Hiring Contact Details:
          </span>
          <span className="text-[10px] text-slate-400">
            Select discovered contact or paste from LinkedIn
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <input
            type="text"
            placeholder="Recruiter Name (e.g. Hiring Lead)"
            value={recruiterName}
            onChange={(e) => setRecruiterName(e.target.value)}
            className="p-1.5 border border-slate-200 rounded text-xs bg-white focus:ring-1 focus:ring-indigo-500"
          />
          <input
            type="text"
            placeholder="Title (e.g. Technical Recruiter)"
            value={recruiterTitle}
            onChange={(e) => setRecruiterTitle(e.target.value)}
            className="p-1.5 border border-slate-200 rounded text-xs bg-white focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            type="email"
            placeholder="Recruiter Email Address"
            value={recruiterEmail}
            onChange={(e) => setRecruiterEmail(e.target.value)}
            className="flex-1 p-1.5 border border-slate-200 rounded text-xs bg-white font-mono focus:ring-1 focus:ring-indigo-500"
          />

          <button
            onClick={handleVerifyEmail}
            disabled={isVerifying || !recruiterEmail}
            className="py-1.5 px-2.5 bg-slate-200 hover:bg-slate-300 text-slate-800 font-semibold text-[11px] rounded transition-colors disabled:opacity-50"
          >
            {isVerifying ? 'Checking...' : 'Verify Email'}
          </button>
        </div>

        {verifyStatus && (
          <div className="flex items-center justify-between text-[11px]">
            <span className="flex items-center gap-1 font-medium text-emerald-700">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              Email Status: {verifyStatus.status.toUpperCase()} ({verifyStatus.confidence}% deliverable)
            </span>
            <span className="text-[10px] text-slate-400">ZeroBounce / Hunter API verified</span>
          </div>
        )}

        <button
          onClick={handleSynthesizeDraft}
          disabled={isSynthesizing}
          className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs rounded-lg shadow-xs transition-colors disabled:opacity-50"
        >
          {isSynthesizing ? 'Synthesizing...' : draft ? 'Regenerate Note' : '✨ Draft Personalized Outreach'}
        </button>
      </div>

      {/* Draft Preview & Editable Output */}
      {draft && (
        <div className="p-3 bg-white border border-slate-200 rounded-lg flex flex-col gap-2 text-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
            <span className="font-bold text-slate-800 text-[11px]">Subject:</span>
            <span className="text-[10px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded font-semibold border border-emerald-200">
              {editableBody.split(/\s+/).filter(Boolean).length} words • CAN-SPAM Compliant
            </span>
          </div>

          <input
            type="text"
            value={editableSubject}
            onChange={(e) => setEditableSubject(e.target.value)}
            className="w-full p-1.5 border border-slate-200 rounded text-xs font-semibold text-slate-800 bg-slate-50 focus:bg-white"
          />

          <textarea
            rows={5}
            value={editableBody}
            onChange={(e) => setEditableBody(e.target.value)}
            className="w-full p-2 border border-slate-200 rounded-lg text-xs text-slate-700 font-mono resize-y bg-slate-50 focus:bg-white leading-relaxed"
          />

          <div className="pt-2 border-t border-slate-100 flex items-center justify-between gap-2">
            <span className="text-[10px] text-slate-400">Includes 1-click opt-out & physical address</span>
            <div className="flex items-center gap-1.5">
              <a
                href={`https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(
                  recruiterEmail || draft.recipient_email || ''
                )}&su=${encodeURIComponent(editableSubject)}&body=${encodeURIComponent(
                  editableBody + '\n\n--\n' + draft.physical_address + '\nOpt-out: ' + draft.opt_out_link
                )}`}
                target="_blank"
                rel="noreferrer"
                className="py-1 px-2.5 bg-red-600 hover:bg-red-700 text-white font-semibold text-[11px] rounded transition-colors shadow-xs inline-flex items-center gap-1"
              >
                ✉️ Open in Gmail
              </a>
              <button
                onClick={handleCopy}
                className="py-1 px-2.5 bg-slate-800 hover:bg-slate-900 text-white font-semibold text-[11px] rounded transition-colors shadow-xs"
              >
                {copied ? '✓ Copied!' : 'Copy Note'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
