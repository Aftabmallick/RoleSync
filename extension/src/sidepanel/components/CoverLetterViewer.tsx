import React, { useState } from 'react';

interface CoverLetterViewerProps {
  targetRole: string;
  companyName: string;
  rawJd: string;
  candidateProfile?: any;
  apiBaseUrl?: string;
  onToast?: (type: 'success' | 'error' | 'warning' | 'info', message: string, title?: string) => void;
}

interface CoverLetterData {
  subject: string;
  salutation: string;
  full_text: string;
  word_count: number;
  matched_skills: string[];
}

export const CoverLetterViewer: React.FC<CoverLetterViewerProps> = ({
  targetRole,
  companyName,
  rawJd,
  candidateProfile,
  apiBaseUrl = 'http://localhost:8000/api/v1',
  onToast,
}) => {
  const [tone, setTone] = useState<'professional' | 'confident' | 'enthusiastic'>('professional');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [coverLetter, setCoverLetter] = useState<CoverLetterData | null>(null);
  const [editableText, setEditableText] = useState<string>('');
  const [copied, setCopied] = useState<boolean>(false);
  const [autofillStatus, setAutofillStatus] = useState<string | null>(null);

  const handleGenerate = async () => {
    setIsGenerating(true);
    setAutofillStatus(null);
    try {
      const res = await fetch(`${apiBaseUrl}/cover-letter/synthesize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_role: targetRole,
          company_name: companyName,
          raw_job_description: rawJd,
          candidate_name: candidateProfile?.personal?.full_name || 'Alex Mercer',
          candidate_summary: candidateProfile?.summary || '',
          master_profile: candidateProfile,
          tone: tone,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setCoverLetter(data);
        setEditableText(data.full_text);
        if (onToast) {
          onToast('success', `Cover letter generated (${data.word_count} words).`, 'Cover Letter Ready');
        }
      } else {
        const errMsg = 'Could not synthesize cover letter. Check if backend server is running.';
        if (onToast) onToast('error', errMsg, 'Synthesis Failed');
        else console.warn(errMsg);
      }
    } catch (err) {
      console.error('[RoleSync UI] Cover letter synthesis error:', err);
      const errMsg = 'Error connecting to backend for cover letter synthesis.';
      if (onToast) onToast('error', errMsg, 'Connection Error');
      else console.warn(errMsg);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopy = () => {
    if (!editableText) return;
    navigator.clipboard.writeText(editableText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleDownloadTxt = () => {
    if (!editableText) return;
    const blob = new Blob([editableText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${companyName.replace(/\s+/g, '_')}_${targetRole.replace(/\s+/g, '_')}_Cover_Letter.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleAutofillToPage = async () => {
    if (!editableText) return;
    setAutofillStatus('Filling cover letter textarea...');

    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tabs[0]?.id) {
        setAutofillStatus('No active browser tab found.');
        return;
      }

      chrome.tabs.sendMessage(
        tabs[0].id,
        {
          action: 'AUTOFILL_COVER_LETTER',
          payload: { coverLetterText: editableText },
        },
        (response) => {
          if (chrome.runtime.lastError || !response || response.status === 'NOT_FOUND') {
            setAutofillStatus('No cover letter field found on page. You can copy text manually.');
          } else {
            setAutofillStatus('✓ Cover letter pasted into application form!');
          }
          setTimeout(() => setAutofillStatus(null), 4000);
        }
      );
    } catch (e) {
      setAutofillStatus('Error communicating with active tab.');
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Tailored Cover Letter
          </h3>
          <p className="text-[11px] text-slate-500">
            ATS-aligned cover letter with your authentic achievements
          </p>
        </div>

        {/* Tone Selector & Generate */}
        <div className="flex items-center gap-1.5">
          <select
            value={tone}
            onChange={(e) => setTone(e.target.value as any)}
            className="text-[11px] p-1 border border-slate-200 rounded-lg bg-slate-50 text-slate-700 font-medium focus:ring-1 focus:ring-indigo-500"
          >
            <option value="professional">Tone: Professional</option>
            <option value="confident">Tone: Confident</option>
            <option value="enthusiastic">Tone: Enthusiastic</option>
          </select>

          <button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="py-1.5 px-3 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold text-xs rounded-lg border border-indigo-200 transition-colors disabled:opacity-50"
          >
            {isGenerating ? 'Synthesizing...' : coverLetter ? 'Regenerate' : '✨ Generate'}
          </button>
        </div>
      </div>

      {coverLetter && (
        <div className="flex flex-col gap-2.5">
          {/* Matched skills pill strip */}
          {coverLetter.matched_skills?.length > 0 && (
            <div className="flex flex-wrap gap-1 p-2 bg-slate-50 rounded-lg border border-slate-200/60">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mr-1 self-center">
                Skills Highlighted:
              </span>
              {coverLetter.matched_skills.map((s, idx) => (
                <span
                  key={idx}
                  className="text-[10px] bg-indigo-50 text-indigo-700 px-1.5 py-0.2 rounded font-semibold border border-indigo-100"
                >
                  ✓ {s}
                </span>
              ))}
            </div>
          )}

          {/* Editable Text Area */}
          <textarea
            rows={7}
            value={editableText}
            onChange={(e) => setEditableText(e.target.value)}
            className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 font-mono leading-relaxed resize-y focus:bg-white focus:ring-1 focus:ring-indigo-500"
          />

          {/* Status Message */}
          {autofillStatus && (
            <span className="text-[11px] text-indigo-700 bg-indigo-50 p-2 rounded-lg border border-indigo-100 font-medium">
              {autofillStatus}
            </span>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-between border-t border-slate-100 pt-2">
            <span className="text-[11px] text-slate-400 font-medium">
              {editableText.split(/\s+/).filter(Boolean).length} words
            </span>

            <div className="flex items-center gap-1.5">
              <button
                onClick={handleAutofillToPage}
                className="py-1 px-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-[11px] rounded transition-colors shadow-xs"
                title="Pasted directly into any cover letter textarea on page"
              >
                ⚡ Autofill into Form
              </button>

              <button
                onClick={handleDownloadTxt}
                className="py-1 px-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-[11px] rounded border border-slate-200 transition-colors"
              >
                💾 .txt
              </button>

              <button
                onClick={handleCopy}
                className="py-1 px-2.5 bg-slate-800 hover:bg-slate-900 text-white font-semibold text-[11px] rounded transition-colors shadow-xs"
              >
                {copied ? '✓ Copied!' : 'Copy'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
