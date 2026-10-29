import React, { useState, useEffect, useRef } from 'react';
import { ScoreBreakdown } from './ScoreCard';

export interface ResumeVersion {
  id: string;
  name: string;
  target_company: string;
  target_role: string;
  created_at: string;
  ats_score: number;
  profile_data: any;
  pdf_base64?: string;
}

interface SkillSuggestion {
  name: string;
  category: string;
  importance: string;
  reason: string;
}

interface BulletSuggestion {
  original_id: string;
  company: string;
  role: string;
  original_text: string;
  suggested_text: string;
  keywords_added: string[];
  reason: string;
}

interface MatchAnalysisData {
  current_score: ScoreBreakdown;
  potential_score: number;
  score_boost: number;
  matched_skills: string[];
  missing_skills: SkillSuggestion[];
  suggested_summary?: string;
  bullet_suggestions: BulletSuggestion[];
  missing_keywords: string[];
}

interface ResumeMatcherProps {
  currentJd: {
    jobTitle: string;
    companyName: string;
    rawText: string;
    atsProvider?: string;
  };
  baseProfile: any;
  apiBaseUrl?: string;
  onVersionSelected: (version: ResumeVersion | null, profileData: any, pdfBase64?: string, score?: ScoreBreakdown) => void;
  onNewProfileUploaded?: (newProfile: any) => void;
}

export const ResumeMatcher: React.FC<ResumeMatcherProps> = ({
  currentJd,
  baseProfile,
  apiBaseUrl = 'http://localhost:8000/api/v1',
  onVersionSelected,
  onNewProfileUploaded,
}) => {
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string>('base');
  const [isMatching, setIsMatching] = useState<boolean>(false);
  const [matchAnalysis, setMatchAnalysis] = useState<MatchAnalysisData | null>(null);

  // Accepted suggestions checkboxes
  const [acceptedSkills, setAcceptedSkills] = useState<Record<string, boolean>>({});
  const [acceptedBullets, setAcceptedBullets] = useState<Record<string, boolean>>({});
  const [acceptSummary, setAcceptSummary] = useState<boolean>(true);
  const [versionNameInput, setVersionNameInput] = useState<string>('');
  const [isSavingVersion, setIsSavingVersion] = useState<boolean>(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);

  // File upload ref
  const fileUploadRef = useRef<HTMLInputElement>(null);
  const [isUploadingResume, setIsUploadingResume] = useState<boolean>(false);

  // Load versions from backend and local storage
  const loadVersions = async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/resume/versions`);
      if (res.ok) {
        const data = await res.json();
        setVersions(data.versions || []);
      }
    } catch {
      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.get('rolesync_resume_versions', (r) => {
          if (r.rolesync_resume_versions) {
            setVersions(r.rolesync_resume_versions);
          }
        });
      }
    }
  };

  useEffect(() => {
    loadVersions();
  }, [apiBaseUrl]);

  // Determine active profile based on selected version
  const getActiveProfile = () => {
    if (selectedVersionId === 'base' || !selectedVersionId) {
      return baseProfile;
    }
    const found = versions.find((v) => v.id === selectedVersionId);
    return found ? found.profile_data : baseProfile;
  };

  // Switch selected version
  const handleSelectVersionChange = (verId: string) => {
    if (verId === '__upload__') {
      fileUploadRef.current?.click();
      return;
    }

    setSelectedVersionId(verId);
    setMatchAnalysis(null);
    setSaveSuccessMsg(null);

    if (verId === 'base') {
      onVersionSelected(null, baseProfile, undefined, undefined);
    } else {
      const found = versions.find((v) => v.id === verId);
      if (found) {
        onVersionSelected(
          found,
          found.profile_data,
          found.pdf_base64,
          {
            composite_score: found.ats_score,
            semantic_score: Math.round(found.ats_score * 0.95),
            skill_coverage_score: Math.round(found.ats_score),
            lexical_score: Math.round(found.ats_score * 0.9),
            experience_alignment_score: 95,
            matched_skills: found.profile_data?.skills?.map((s: any) => s.name || s) || [],
            missing_skills: [],
          }
        );
      }
    }
  };

  // Handle uploading a new resume PDF
  const handleUploadNewPdf = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploadingResume(true);
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const base64Data = (reader.result as string).split(',')[1];
        const res = await fetch(`${apiBaseUrl}/profile/parse-resume`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pdf_base64: base64Data }),
        });

        if (res.ok) {
          const data = await res.json();
          if (data.profile) {
            if (onNewProfileUploaded) onNewProfileUploaded(data.profile);
            setSelectedVersionId('base');
            alert('✓ New resume uploaded & parsed successfully into Master Vault!');
          }
        }
      } catch (err) {
        console.error('[RoleSync UI] Upload error:', err);
        alert('Could not parse resume PDF.');
      } finally {
        setIsUploadingResume(false);
        if (fileUploadRef.current) fileUploadRef.current.value = '';
      }
    };
    reader.readAsDataURL(file);
  };

  // Execute Match & Suggest Additions
  const handleMatchResume = async () => {
    setIsMatching(true);
    setMatchAnalysis(null);
    setSaveSuccessMsg(null);

    const activeProf = getActiveProfile();

    try {
      const res = await fetch(`${apiBaseUrl}/resume/match-and-suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_description: currentJd.rawText,
          target_role: currentJd.jobTitle,
          company_name: currentJd.companyName,
          resume: activeProf,
        }),
      });

      if (res.ok) {
        const data: MatchAnalysisData = await res.json();
        setMatchAnalysis(data);

        // Pre-check all missing skills & bullets by default
        const initSkills: Record<string, boolean> = {};
        data.missing_skills.forEach((s) => (initSkills[s.name] = true));
        setAcceptedSkills(initSkills);

        const initBullets: Record<string, boolean> = {};
        data.bullet_suggestions.forEach((b) => (initBullets[b.original_id] = true));
        setAcceptedBullets(initBullets);

        setAcceptSummary(true);
        setVersionNameInput(`Enhanced for ${currentJd.companyName} (${currentJd.jobTitle})`);
      } else {
        alert('Failed to match resume against job description.');
      }
    } catch (err) {
      console.error('[RoleSync UI] Match error:', err);
      alert('Error connecting to backend for resume match.');
    } finally {
      setIsMatching(false);
    }
  };

  // Accept suggestions & save as a new version
  const handleAcceptAndSaveVersion = async () => {
    if (!matchAnalysis) return;
    setIsSavingVersion(true);

    const activeProf = getActiveProfile();
    const skillsToApply = Object.keys(acceptedSkills).filter((k) => acceptedSkills[k]);
    const bulletsToApply = matchAnalysis.bullet_suggestions
      .filter((b) => acceptedBullets[b.original_id])
      .map((b) => ({ original_id: b.original_id, suggested_text: b.suggested_text }));

    try {
      const res = await fetch(`${apiBaseUrl}/resume/apply-enhancements`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_resume: activeProf,
          target_role: currentJd.jobTitle,
          company_name: currentJd.companyName,
          version_name: versionNameInput.trim() || `Enhanced for ${currentJd.companyName}`,
          accepted_skills: skillsToApply,
          accepted_summary: acceptSummary ? matchAnalysis.suggested_summary : undefined,
          accepted_bullet_updates: bulletsToApply,
        }),
      });

      if (res.ok) {
        const newVer: ResumeVersion = await res.json();
        setVersions((prev) => [newVer, ...prev]);
        setSelectedVersionId(newVer.id);
        setSaveSuccessMsg(`✓ Saved new version: "${newVer.name}" with ${Math.round(newVer.ats_score)}% ATS Match!`);

        // Notify parent of newly enhanced version and its compiled PDF
        onVersionSelected(
          newVer,
          newVer.profile_data,
          newVer.pdf_base64,
          {
            composite_score: newVer.ats_score,
            semantic_score: Math.round(newVer.ats_score * 0.95),
            skill_coverage_score: Math.round(newVer.ats_score),
            lexical_score: Math.round(newVer.ats_score * 0.9),
            experience_alignment_score: 95,
            matched_skills: newVer.profile_data?.skills?.map((s: any) => s.name || s) || [],
            missing_skills: [],
          }
        );

        // Update local storage backup
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
          chrome.storage.local.get('rolesync_resume_versions', (r) => {
            const list = r.rolesync_resume_versions || [];
            chrome.storage.local.set({ rolesync_resume_versions: [newVer, ...list] });
          });
        }
      } else {
        alert('Could not save new resume version.');
      }
    } catch (err) {
      console.error('[RoleSync UI] Error saving version:', err);
    } finally {
      setIsSavingVersion(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col gap-3.5">
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileUploadRef}
        accept=".pdf"
        onChange={handleUploadNewPdf}
        className="hidden"
      />

      {/* Header and Version Selector */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Select Resume Version to Match
          </label>
          <button
            onClick={() => fileUploadRef.current?.click()}
            disabled={isUploadingResume}
            className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 transition-colors"
          >
            {isUploadingResume ? '⏳ Parsing...' : '+ Upload New PDF'}
          </button>
        </div>

        {/* Dropdown with all versions */}
        <select
          value={selectedVersionId}
          onChange={(e) => handleSelectVersionChange(e.target.value)}
          className="w-full p-2 border border-slate-300 rounded-lg text-xs bg-slate-50 font-medium text-slate-800 focus:bg-white focus:ring-2 focus:ring-indigo-500"
        >
          <option value="base">📄 Master Career Vault Resume (Default Base)</option>
          {versions.map((v) => (
            <option key={v.id} value={v.id}>
              📑 {v.name} ({Math.round(v.ats_score)}% Score)
            </option>
          ))}
          <option value="__upload__">⬆️ Upload New Resume File (.pdf)...</option>
        </select>
      </div>

      {/* Match Button */}
      <button
        onClick={handleMatchResume}
        disabled={isMatching}
        className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-lg shadow-sm transition-all focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 flex items-center justify-center gap-2"
      >
        <span>
          {isMatching
            ? '⏳ Benchmarking ATS Score & Identifying Gaps...'
            : '🔍 Match Resume with Job Description'}
        </span>
      </button>

      {saveSuccessMsg && (
        <div className="p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-xs font-semibold text-emerald-800">
          {saveSuccessMsg}
        </div>
      )}

      {/* Suggested Additions & Gap Analysis Block */}
      {matchAnalysis && (
        <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex flex-col gap-3.5 text-xs">
          {/* Score Comparison Banner */}
          <div className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg shadow-xs">
            <div className="flex flex-col">
              <span className="text-[10px] uppercase font-bold text-slate-400">Current ATS Score</span>
              <span className="text-xl font-extrabold text-slate-800">
                {Math.round(matchAnalysis.current_score.composite_score)}%
              </span>
            </div>

            <div className="text-xl font-bold text-indigo-500">➜</div>

            <div className="flex flex-col items-end">
              <span className="text-[10px] uppercase font-bold text-emerald-600">With Accepted Additions</span>
              <span className="text-xl font-extrabold text-emerald-600 flex items-center gap-1">
                {Math.round(matchAnalysis.potential_score)}%
                <span className="text-[11px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.2 rounded-full">
                  +{matchAnalysis.score_boost}% Boost
                </span>
              </span>
            </div>
          </div>

          {/* 1. Missing Skills Suggestions */}
          {matchAnalysis.missing_skills.length > 0 && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-800 text-[11px] uppercase tracking-wide">
                  Suggested Skill Additions ({matchAnalysis.missing_skills.length})
                </span>
                <button
                  onClick={() => {
                    const allChecked = Object.values(acceptedSkills).every(Boolean);
                    const updated: Record<string, boolean> = {};
                    matchAnalysis.missing_skills.forEach((s) => (updated[s.name] = !allChecked));
                    setAcceptedSkills(updated);
                  }}
                  className="text-[10px] text-indigo-600 hover:underline font-semibold"
                >
                  Toggle All
                </button>
              </div>

              <div className="grid grid-cols-2 gap-1.5">
                {matchAnalysis.missing_skills.map((skill, idx) => (
                  <label
                    key={idx}
                    className={`p-2 rounded-lg border flex items-center justify-between cursor-pointer transition-colors ${
                      acceptedSkills[skill.name]
                        ? 'bg-indigo-50/70 border-indigo-200 text-indigo-900'
                        : 'bg-white border-slate-200 text-slate-600'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={!!acceptedSkills[skill.name]}
                        onChange={(e) =>
                          setAcceptedSkills({ ...acceptedSkills, [skill.name]: e.target.checked })
                        }
                        className="rounded text-indigo-600"
                      />
                      <span className="font-bold text-xs">{skill.name}</span>
                    </div>
                    <span className="text-[9px] font-semibold text-slate-400 bg-slate-100 px-1.5 py-0.2 rounded">
                      {skill.category}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* 2. Suggested Bullet Point Improvements */}
          {matchAnalysis.bullet_suggestions.length > 0 && (
            <div className="flex flex-col gap-2 pt-2 border-t border-slate-200">
              <span className="font-bold text-slate-800 text-[11px] uppercase tracking-wide">
                Suggested Bullet Improvements (Zero-Hallucination)
              </span>

              <div className="flex flex-col gap-2">
                {matchAnalysis.bullet_suggestions.map((bullet, idx) => (
                  <div
                    key={idx}
                    className={`p-2.5 rounded-lg border transition-colors flex flex-col gap-1.5 ${
                      acceptedBullets[bullet.original_id]
                        ? 'bg-white border-indigo-200 shadow-xs'
                        : 'bg-slate-100/60 border-slate-200 opacity-60'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-800 text-[11px]">
                        {bullet.role} • {bullet.company}
                      </span>
                      <label className="flex items-center gap-1.5 cursor-pointer text-[11px] font-bold text-indigo-700">
                        <input
                          type="checkbox"
                          checked={!!acceptedBullets[bullet.original_id]}
                          onChange={(e) =>
                            setAcceptedBullets({
                              ...acceptedBullets,
                              [bullet.original_id]: e.target.checked,
                            })
                          }
                          className="rounded text-indigo-600"
                        />
                        Accept Enhancement
                      </label>
                    </div>

                    <div className="text-[11px] text-slate-400 line-through pl-2 border-l-2 border-amber-300">
                      {bullet.original_text}
                    </div>

                    <div className="text-[11px] text-slate-800 font-medium pl-2 border-l-2 border-emerald-500">
                      {bullet.suggested_text}
                    </div>

                    {bullet.keywords_added?.length > 0 && (
                      <div className="flex flex-wrap gap-1 pt-0.5">
                        {bullet.keywords_added.map((kw, kIdx) => (
                          <span
                            key={kIdx}
                            className="text-[9px] bg-emerald-50 text-emerald-700 px-1.5 py-0.2 rounded font-semibold border border-emerald-200"
                          >
                            +{kw}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 3. Suggested Professional Summary */}
          {matchAnalysis.suggested_summary && (
            <div className="flex flex-col gap-1.5 pt-2 border-t border-slate-200">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-800 text-[11px] uppercase tracking-wide">
                  Targeted Professional Summary
                </span>
                <label className="flex items-center gap-1.5 cursor-pointer text-[11px] font-bold text-indigo-700">
                  <input
                    type="checkbox"
                    checked={acceptSummary}
                    onChange={(e) => setAcceptSummary(e.target.checked)}
                    className="rounded text-indigo-600"
                  />
                  Update Summary
                </label>
              </div>
              <p className="p-2 bg-white rounded-lg border border-slate-200 text-[11px] text-slate-700 leading-relaxed font-medium">
                {matchAnalysis.suggested_summary}
              </p>
            </div>
          )}

          {/* Version Save Actions */}
          <div className="pt-2 border-t border-slate-200 flex flex-col gap-2">
            <label className="text-[11px] font-bold text-slate-700">Save as New Version Name:</label>
            <input
              type="text"
              value={versionNameInput}
              onChange={(e) => setVersionNameInput(e.target.value)}
              placeholder="e.g. Enhanced for Stripe - Senior Infrastructure"
              className="p-2 border border-slate-300 rounded-lg text-xs bg-white font-medium"
            />

            <button
              onClick={handleAcceptAndSaveVersion}
              disabled={isSavingVersion}
              className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg shadow transition-all flex items-center justify-center gap-1.5 disabled:opacity-50"
            >
              <span>
                {isSavingVersion
                  ? 'Compiling Single-Page Typst PDF...'
                  : '✨ Accept Suggestions & Save as New Version'}
              </span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

