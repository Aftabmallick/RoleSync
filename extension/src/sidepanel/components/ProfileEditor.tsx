import React, { useState, useEffect, useRef } from 'react';

export interface PersonalInfo {
  full_name: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  github: string;
}

export interface SkillItem {
  name: string;
  category?: string;
}

export interface BulletPoint {
  id: string;
  text: string;
}

export interface ExperienceItem {
  company: string;
  role: string;
  start_date: string;
  end_date: string;
  location: string;
  bullets: BulletPoint[];
}

export interface EducationItem {
  institution: string;
  degree: string;
  field: string;
  end_date: string;
  gpa: string;
}

export interface ProjectItem {
  name: string;
  subtitle?: string;
  technologies?: string;
  link?: string;
  start_date?: string;
  end_date?: string;
  bullets: BulletPoint[];
}

export interface PreferencesData {
  legally_authorized?: boolean;
  requires_sponsorship?: boolean;
  gender?: string;
  veteran_status?: string;
  disability_status?: string;
}

export interface MasterProfileData {
  personal: PersonalInfo;
  skills: SkillItem[];
  experience: ExperienceItem[];
  projects?: ProjectItem[];
  education: EducationItem[];
  summary: string;
  preferences?: PreferencesData;
}

const DEFAULT_PROFILE: MasterProfileData = {
  personal: {
    full_name: 'Alex Mercer',
    email: 'alex@mercer.dev',
    phone: '+1 (555) 019-2834',
    location: 'San Francisco, CA',
    linkedin: 'linkedin.com/in/alex-mercer',
    github: 'github.com/alexmercer',
  },
  preferences: {
    legally_authorized: true,
    requires_sponsorship: false,
    gender: 'Decline to self-identify',
    veteran_status: 'I am not a protected veteran',
    disability_status: 'No, I do not have a disability',
  },
  skills: [
    { name: 'Python', category: 'Languages' },
    { name: 'FastAPI', category: 'Frameworks' },
    { name: 'PostgreSQL', category: 'Databases' },
    { name: 'Docker', category: 'DevOps' },
    { name: 'Kubernetes', category: 'DevOps' },
    { name: 'Redis', category: 'Databases' },
  ],
  experience: [
    {
      company: 'Apex Systems',
      role: 'Senior Software Engineer',
      start_date: '2021',
      end_date: 'Present',
      location: 'San Francisco, CA',
      bullets: [
        {
          id: 'b_apex_1',
          text: 'Refactored payment gateway microservice, reducing response latency by 1.5s and saving $1,500,000 annually across 10x traffic volume.',
        },
        {
          id: 'b_apex_2',
          text: 'Architected PostgreSQL distributed read replicas improving read throughput by 35%.',
        },
      ],
    },
  ],
  projects: [
    {
      name: 'TitanRAG',
      subtitle: 'Multi-Tenant Multimodal RAG Platform',
      technologies: 'Python, FastAPI, PostgreSQL (RLS), Qdrant, Celery, LiteLLM, Redis',
      link: 'github.com/alexmercer/titanrag',
      start_date: '2024',
      end_date: 'Present',
      bullets: [
        {
          id: 'b_proj_1',
          text: 'Engineered a multi-tenant multimodal RAG platform leveraging PostgreSQL Row-Level Security (RLS) and tenant-isolated collections in Qdrant.',
        },
      ],
    },
  ],
  education: [
    {
      institution: 'University of California, Berkeley',
      degree: 'B.S.',
      field: 'Computer Science',
      end_date: '2020',
      gpa: '3.85',
    },
  ],
  summary:
    'Senior Software Engineer specializing in scalable architecture, event-driven distributed systems, and high-performance cloud engineering.',
};

export const BLANK_PROFILE: MasterProfileData = {
  personal: {
    full_name: '',
    email: '',
    phone: '',
    location: '',
    linkedin: '',
    github: '',
  },
  skills: [],
  experience: [],
  projects: [],
  education: [],
  summary: '',
};

interface ProfileEditorProps {
  onSave?: (profile: MasterProfileData) => void;
  apiBaseUrl?: string;
  onToast?: (type: 'success' | 'error' | 'warning' | 'info', message: string, title?: string) => void;
}

export const ProfileEditor: React.FC<ProfileEditorProps> = ({
  onSave,
  apiBaseUrl = 'http://localhost:8000/api/v1',
  onToast,
}) => {
  const [profile, setProfile] = useState<MasterProfileData>(DEFAULT_PROFILE);
  const [newSkill, setNewSkill] = useState<string>('');
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  // Resume Upload / Parse states
  const [isParsingResume, setIsParsingResume] = useState<boolean>(false);
  const [parseNotification, setParseNotification] = useState<string | null>(null);
  const [showPasteText, setShowPasteText] = useState<boolean>(false);
  const [pastedResumeText, setPastedResumeText] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const jsonInputRef = useRef<HTMLInputElement>(null);

  // New experience form states
  const [expCompany, setExpCompany] = useState<string>('');
  const [expRole, setExpRole] = useState<string>('');
  const [expStart, setExpStart] = useState<string>('');
  const [expEnd, setExpEnd] = useState<string>('Present');
  const [expLocation, setExpLocation] = useState<string>('Remote');
  const [expBullet, setExpBullet] = useState<string>('');

  // New education form states
  const [eduInst, setEduInst] = useState<string>('');
  const [eduDegree, setEduDegree] = useState<string>('B.S.');
  const [eduField, setEduField] = useState<string>('Computer Science');
  const [eduYear, setEduYear] = useState<string>('2021');
  const [eduGpa, setEduGpa] = useState<string>('');

  // Active bullet addition state for existing experience
  const [activeExpBulletIdx, setActiveExpBulletIdx] = useState<number | null>(null);
  const [newBulletText, setNewBulletText] = useState<string>('');

  // New project form states
  const [projName, setProjName] = useState<string>('');
  const [projSubtitle, setProjSubtitle] = useState<string>('');
  const [projTech, setProjTech] = useState<string>('');
  const [projLink, setProjLink] = useState<string>('');
  const [projBullet, setProjBullet] = useState<string>('');
  const [activeProjBulletIdx, setActiveProjBulletIdx] = useState<number | null>(null);
  const [newProjBulletText, setNewProjBulletText] = useState<string>('');

  useEffect(() => {
    // 1. Load from extension local storage
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get('rolesync_master_profile', (res) => {
        if (res.rolesync_master_profile) {
          setProfile(res.rolesync_master_profile);
        } else {
          // Fetch from backend
          fetch(`${apiBaseUrl}/profile`)
            .then((r) => r.json())
            .then((data) => {
              if (data.profile) {
                setProfile(data.profile);
              }
            })
            .catch((e) => console.log('[RoleSync] Backend offline, using defaults:', e));
        }
      });
    }
  }, [apiBaseUrl]);

  // Handle PDF Resume File Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsParsingResume(true);
    setParseNotification('Reading document and extracting text...');

    const reader = new FileReader();

    reader.onerror = () => {
      console.error('[RoleSync] FileReader error');
      setParseNotification('✕ Could not read file from disk.');
      setIsParsingResume(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    };

    reader.onload = async () => {
      try {
        const base64Data = (reader.result as string).split(',')[1];
        setParseNotification('Extracting skills via canonical taxonomy & parsing experience...');

        const res = await fetch(`${apiBaseUrl}/profile/parse-resume`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pdf_base64: base64Data }),
        });

        if (!res.ok) {
          let errDetail = `Server returned ${res.status}`;
          try {
            const errJson = await res.json();
            if (errJson?.detail) errDetail = errJson.detail;
          } catch {}
          throw new Error(errDetail);
        }

        const data = await res.json();
        if (data.profile) {
          setProfile(data.profile);
          setParseNotification(
            `✓ Successfully parsed resume! Detected ${data.detected_skills_count} skills & ${data.detected_experience_count} roles. Review and click Save & Encrypt.`
          );
          if (onSave) onSave(data.profile);
        }
      } catch (err: any) {
        console.error('[RoleSync] Resume parse error:', err);
        setParseNotification(`✕ Resume parsing error: ${err.message || 'Check server connection'}`);
      } finally {
        setIsParsingResume(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    };

    reader.readAsDataURL(file);
  };

  // Handle Raw Text Parse
  const handleParseText = async () => {
    if (!pastedResumeText.trim()) return;
    setIsParsingResume(true);
    setParseNotification('Extracting entities and structuring profile...');

    try {
      const res = await fetch(`${apiBaseUrl}/profile/parse-resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_text: pastedResumeText }),
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const data = await res.json();
      if (data.profile) {
        setProfile(data.profile);
        setShowPasteText(false);
        setPastedResumeText('');
        setParseNotification(
          `✓ Structured ${data.detected_skills_count} skills and ${data.detected_experience_count} career experiences.`
        );
        if (onSave) onSave(data.profile);
      }
    } catch (err) {
      console.error('[RoleSync] Text parse error:', err);
      setParseNotification('✕ Failed to parse resume text. Please ensure backend is reachable.');
    } finally {
      setIsParsingResume(false);
    }
  };

  const handleSaveVault = async () => {
    setIsSaving(true);
    setSaveStatus('Encrypting with AES-256 HKDF...');

    try {
      // 1. Save locally in extension storage
      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        await chrome.storage.local.set({ rolesync_master_profile: profile });
      }

      // 2. Sync to backend vault
      const res = await fetch(`${apiBaseUrl}/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });

      if (res.ok) {
        const data = await res.json();
        setSaveStatus(`✓ Saved & Encrypted (v${data.version})`);
      } else {
        setSaveStatus('✓ Saved locally in browser vault');
      }

      if (onSave) {
        onSave(profile);
      }
    } catch (e) {
      console.warn('[RoleSync] Could not reach backend, stored locally:', e);
      setSaveStatus('✓ Saved locally in browser storage');
      if (onSave) {
        onSave(profile);
      }
    } finally {
      setIsSaving(false);
      setTimeout(() => setSaveStatus(null), 4000);
    }
  };

  const handleAddSkill = () => {
    if (!newSkill.trim()) return;
    const clean = newSkill.trim();
    if (!profile.skills.some((s) => s.name.toLowerCase() === clean.toLowerCase())) {
      setProfile({
        ...profile,
        skills: [...profile.skills, { name: clean, category: 'Technical' }],
      });
    }
    setNewSkill('');
  };

  const handleRemoveSkill = (skillName: string) => {
    setProfile({
      ...profile,
      skills: profile.skills.filter((s) => s.name !== skillName),
    });
  };

  const handleAddExperience = () => {
    if (!expCompany.trim() || !expRole.trim()) return;
    const newExp: ExperienceItem = {
      company: expCompany.trim(),
      role: expRole.trim(),
      start_date: expStart.trim() || '2021',
      end_date: expEnd.trim() || 'Present',
      location: expLocation.trim() || 'Remote',
      bullets: expBullet.trim()
        ? [{ id: `b_${Date.now()}`, text: expBullet.trim() }]
        : [],
    };

    setProfile({
      ...profile,
      experience: [newExp, ...profile.experience],
    });

    setExpCompany('');
    setExpRole('');
    setExpStart('');
    setExpEnd('Present');
    setExpBullet('');
  };

  const handleRemoveExperience = (index: number) => {
    const updated = [...profile.experience];
    updated.splice(index, 1);
    setProfile({ ...profile, experience: updated });
  };

  const handleAddBulletToExperience = (expIndex: number) => {
    if (!newBulletText.trim()) return;
    const updated = [...profile.experience];
    updated[expIndex].bullets.push({
      id: `b_${Date.now()}`,
      text: newBulletText.trim(),
    });
    setProfile({ ...profile, experience: updated });
    setNewBulletText('');
    setActiveExpBulletIdx(null);
  };

  const handleRemoveBullet = (expIndex: number, bulletIndex: number) => {
    const updated = [...profile.experience];
    updated[expIndex].bullets.splice(bulletIndex, 1);
    setProfile({ ...profile, experience: updated });
  };

  const handleAddProject = () => {
    if (!projName.trim()) return;
    const newProj: ProjectItem = {
      name: projName.trim(),
      subtitle: projSubtitle.trim() || 'Featured Project',
      technologies: projTech.trim(),
      link: projLink.trim(),
      start_date: '2024',
      end_date: 'Present',
      bullets: projBullet.trim()
        ? [{ id: `b_proj_${Date.now()}`, text: projBullet.trim() }]
        : [],
    };
    setProfile({
      ...profile,
      projects: [...(profile.projects || []), newProj],
    });
    setProjName('');
    setProjSubtitle('');
    setProjTech('');
    setProjLink('');
    setProjBullet('');
  };

  const handleRemoveProject = (index: number) => {
    const updated = [...(profile.projects || [])];
    updated.splice(index, 1);
    setProfile({ ...profile, projects: updated });
  };

  const handleAddBulletToProject = (projIndex: number) => {
    if (!newProjBulletText.trim()) return;
    const updated = [...(profile.projects || [])];
    updated[projIndex].bullets.push({
      id: `b_proj_${Date.now()}`,
      text: newProjBulletText.trim(),
    });
    setProfile({ ...profile, projects: updated });
    setNewProjBulletText('');
    setActiveProjBulletIdx(null);
  };

  const handleRemoveBulletFromProject = (projIndex: number, bulletIndex: number) => {
    const updated = [...(profile.projects || [])];
    updated[projIndex].bullets.splice(bulletIndex, 1);
    setProfile({ ...profile, projects: updated });
  };

  const handleAddEducation = () => {
    if (!eduInst.trim()) return;
    const newEdu: EducationItem = {
      institution: eduInst.trim(),
      degree: eduDegree.trim() || 'B.S.',
      field: eduField.trim() || 'Computer Science',
      end_date: eduYear.trim() || '2021',
      gpa: eduGpa.trim(),
    };
    setProfile({
      ...profile,
      education: [...profile.education, newEdu],
    });
    setEduInst('');
    setEduGpa('');
  };

  const handleRemoveEducation = (index: number) => {
    const updated = [...profile.education];
    updated.splice(index, 1);
    setProfile({ ...profile, education: updated });
  };

  // Export JSON backup
  const handleExportJson = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(profile, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `RoleSync_MasterProfile_${Date.now()}.json`);
    downloadAnchor.click();
  };

  const handleImportJson = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target?.result as string);
        if (parsed.personal && parsed.skills) {
          setProfile(parsed);
          setSaveStatus('✓ Master Profile imported from JSON!');
          setTimeout(() => setSaveStatus(null), 3000);
          if (onToast) onToast('success', 'Master Profile imported from JSON backup.', 'Profile Imported');
        } else {
          if (onToast) onToast('error', 'Invalid profile JSON structure.', 'Import Failed');
          else setSaveStatus('✕ Invalid profile JSON structure');
        }
      } catch (err) {
        if (onToast) onToast('error', 'Could not parse JSON file.', 'Parse Error');
        else setSaveStatus('✕ Could not parse JSON file');
      }
    };
    reader.readAsText(file);
    if (jsonInputRef.current) jsonInputRef.current.value = '';
  };

  const handleResetDefault = () => {
    if (confirm('Reset Master Profile to sample data (Alex Mercer)?')) {
      setProfile(DEFAULT_PROFILE);
      setSaveStatus('✓ Reset to sample profile');
      setTimeout(() => setSaveStatus(null), 3000);
      if (onToast) onToast('info', 'Reset Master Profile to demo profile (Alex Mercer).', 'Profile Reset');
    }
  };

  const handleClearProfile = () => {
    if (confirm('Clear entire Master Profile and start with a blank form?')) {
      setProfile(BLANK_PROFILE);
      setSaveStatus('✓ Profile cleared');
      setTimeout(() => setSaveStatus(null), 3000);
      if (onToast) onToast('info', 'Profile cleared. Enter your details or upload a resume PDF.', 'Blank Profile Started');
    }
  };

  return (
    <div className="flex flex-col gap-4 text-slate-800 pb-8">
      {/* Vault Header Banner */}
      <div className="p-3 bg-gradient-to-r from-indigo-50 to-blue-50 border border-indigo-100 rounded-xl flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold text-sm shrink-0">
          🔒
        </div>
        <div>
          <h2 className="text-xs font-bold text-indigo-900 uppercase tracking-wider">
            Zero-Trust Master Career Vault
          </h2>
          <p className="text-[11px] text-indigo-700 leading-relaxed mt-0.5">
            RoleSync uses this vault as your <strong>sole source of truth</strong>. All tailored resumes are mathematically verified to entail only authentic metrics stored here.
          </p>
        </div>
      </div>

      {/* 📄 Base Resume Dropzone & Auto-Parser */}
      <div className="p-4 bg-white rounded-xl border-2 border-dashed border-indigo-200 hover:border-indigo-400 transition-colors shadow-sm flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">📄</span>
            <div>
              <h3 className="text-xs font-bold text-slate-900">Upload Base Resume (PDF)</h3>
              <p className="text-[10px] text-slate-500">Auto-extracts contact info, canonical skills, roles & verified metrics</p>
            </div>
          </div>
          <button
            onClick={() => setShowPasteText(!showPasteText)}
            className="text-[10px] font-semibold text-indigo-600 hover:text-indigo-800 underline"
          >
            {showPasteText ? 'Hide Text' : 'Paste Text'}
          </button>
        </div>

        <input
          type="file"
          ref={fileInputRef}
          accept=".pdf,.txt"
          onChange={handleFileUpload}
          className="hidden"
        />

        <div className="flex items-center gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isParsingResume}
            className="flex-1 py-2 px-3 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-700 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1.5 shadow-sm disabled:opacity-50"
          >
            <span>{isParsingResume ? '⏳ Parsing Document...' : '⬆ Choose Resume PDF'}</span>
          </button>
        </div>

        {parseNotification && (
          <div className="p-2 bg-emerald-50 border border-emerald-200 rounded-lg text-[11px] text-emerald-800 font-medium">
            {parseNotification}
          </div>
        )}

        {showPasteText && (
          <div className="pt-2 flex flex-col gap-2 border-t border-slate-100">
            <textarea
              rows={4}
              placeholder="Paste plain resume text here..."
              value={pastedResumeText}
              onChange={(e) => setPastedResumeText(e.target.value)}
              className="w-full p-2 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
            <button
              onClick={handleParseText}
              disabled={isParsingResume || !pastedResumeText.trim()}
              className="py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50"
            >
              Parse Text to Vault
            </button>
          </div>
        )}
      </div>

      {/* Save Button & Status bar */}
      <div className="flex items-center justify-between gap-2 sticky top-0 bg-slate-50/95 backdrop-blur py-2 z-10">
        <button
          onClick={handleSaveVault}
          disabled={isSaving}
          className="py-2 px-3.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-sm transition-all focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 flex items-center gap-1.5"
        >
          <span>{isSaving ? 'Encrypting...' : 'Save & Encrypt Vault'}</span>
        </button>
        <div className="flex items-center gap-1.5">
          <input
            type="file"
            ref={jsonInputRef}
            accept=".json"
            onChange={handleImportJson}
            className="hidden"
          />
          <button
            onClick={() => jsonInputRef.current?.click()}
            className="py-1 px-2 text-[10px] font-semibold text-slate-600 hover:text-slate-900 bg-white border border-slate-200 rounded-lg shadow-xs"
            title="Import JSON backup"
          >
            Import JSON
          </button>
          <button
            onClick={handleExportJson}
            className="py-1 px-2 text-[10px] font-semibold text-slate-600 hover:text-slate-900 bg-white border border-slate-200 rounded-lg shadow-xs"
            title="Download JSON backup"
          >
            Export JSON
          </button>
          <button
            onClick={handleClearProfile}
            className="py-1 px-2 text-[10px] font-semibold text-rose-500 hover:text-rose-700 bg-white border border-rose-200 rounded-lg shadow-xs"
            title="Start with a blank profile"
          >
            Clear / Start Fresh
          </button>
          <button
            onClick={handleResetDefault}
            className="py-1 px-2 text-[10px] font-semibold text-slate-400 hover:text-slate-600 bg-white border border-slate-200 rounded-lg shadow-xs"
            title="Reset to default sample profile (Alex Mercer)"
          >
            Demo Profile
          </button>
          {saveStatus && (
            <span className="text-[11px] font-semibold text-emerald-600 bg-emerald-50 px-2 py-1 rounded border border-emerald-200">
              {saveStatus}
            </span>
          )}
        </div>
      </div>

      {/* Contact Info Card */}
      <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col gap-3">
        <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
          1. Contact Information
        </h3>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Full Name</label>
            <input
              type="text"
              value={profile.personal.full_name}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  personal: { ...profile.personal, full_name: e.target.value },
                })
              }
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Email</label>
            <input
              type="email"
              value={profile.personal.email}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  personal: { ...profile.personal, email: e.target.value },
                })
              }
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Phone</label>
            <input
              type="text"
              value={profile.personal.phone}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  personal: { ...profile.personal, phone: e.target.value },
                })
              }
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Location</label>
            <input
              type="text"
              value={profile.personal.location}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  personal: { ...profile.personal, location: e.target.value },
                })
              }
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>
          <div className="col-span-2">
            <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">LinkedIn Handle/URL</label>
            <input
              type="text"
              value={profile.personal.linkedin}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  personal: { ...profile.personal, linkedin: e.target.value },
                })
              }
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>
          <div className="col-span-2">
            <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">GitHub Profile URL</label>
            <input
              type="text"
              value={profile.personal.github}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  personal: { ...profile.personal, github: e.target.value },
                })
              }
              className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* Professional Summary */}
      <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            2. Executive Bio / Summary
          </h3>
          <span className="text-[10px] text-slate-400">Max 600 chars</span>
        </div>
        <textarea
          rows={3}
          maxLength={600}
          value={profile.summary}
          onChange={(e) => setProfile({ ...profile, summary: e.target.value })}
          className="w-full p-2.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none resize-none leading-relaxed"
          placeholder="Brief summary of your professional background..."
        />
      </div>

      {/* Skills Vault */}
      <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            3. Skills Vault ({profile.skills.length})
          </h3>
          <span className="text-[11px] text-slate-400">Canonical taxonomy</span>
        </div>

        {/* Add Skill input */}
        <div className="flex gap-2">
          <input
            type="text"
            value={newSkill}
            onChange={(e) => setNewSkill(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddSkill()}
            placeholder="Add technology (e.g. React, Go, AWS)..."
            className="flex-1 px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
          />
          <button
            onClick={handleAddSkill}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold rounded-lg shadow-sm"
          >
            + Add
          </button>
        </div>

        {/* Skill badges */}
        <div className="flex flex-wrap gap-1.5 pt-1 max-h-36 overflow-y-auto">
          {profile.skills.map((s, idx) => (
            <span
              key={idx}
              className="inline-flex items-center gap-1.5 bg-indigo-50 text-indigo-700 text-[11px] font-medium px-2 py-0.5 rounded-md border border-indigo-100"
            >
              {s.name}
              <button
                onClick={() => handleRemoveSkill(s.name)}
                className="text-indigo-400 hover:text-rose-600 font-bold ml-0.5 text-xs"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* Career Experience Vault */}
      <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col gap-3">
        <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
          4. Career Experience Vault ({profile.experience.length})
        </h3>

        {/* Existing roles */}
        <div className="space-y-3">
          {profile.experience.map((exp, idx) => (
            <div key={idx} className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex flex-col gap-2 text-xs relative group">
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="font-bold text-slate-900">{exp.role}</h4>
                  <p className="text-[11px] text-slate-600 font-medium">
                    {exp.company} • {exp.start_date} - {exp.end_date} {exp.location && `• ${exp.location}`}
                  </p>
                </div>
                <button
                  onClick={() => handleRemoveExperience(idx)}
                  className="text-slate-400 hover:text-rose-600 text-xs font-bold p-1"
                  title="Delete role"
                >
                  ✕
                </button>
              </div>

              {/* Bullet points */}
              <ul className="space-y-1.5 pl-1 text-slate-700 text-[11px]">
                {exp.bullets.map((b, bIdx) => (
                  <li key={bIdx} className="flex items-start gap-1.5 group/bullet">
                    <span className="text-indigo-500 font-bold">•</span>
                    <span className="flex-1 leading-snug">{b.text}</span>
                    <button
                      onClick={() => handleRemoveBullet(idx, bIdx)}
                      className="opacity-0 group-hover/bullet:opacity-100 text-rose-500 hover:text-rose-700 font-bold text-xs"
                      title="Remove bullet"
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>

              {/* Inline Bullet Adder */}
              {activeExpBulletIdx === idx ? (
                <div className="mt-1 flex flex-col gap-1.5 pt-1.5 border-t border-slate-200">
                  <textarea
                    rows={2}
                    placeholder="Enter verified accomplishment with measurable metrics (e.g. Scaled database by 40%)..."
                    value={newBulletText}
                    onChange={(e) => setNewBulletText(e.target.value)}
                    className="p-1.5 border border-slate-300 rounded text-xs resize-none"
                  />
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => setActiveExpBulletIdx(null)}
                      className="px-2 py-1 text-[11px] text-slate-500 hover:text-slate-700 font-semibold"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleAddBulletToExperience(idx)}
                      className="px-3 py-1 bg-indigo-600 text-white rounded text-[11px] font-semibold"
                    >
                      Save Bullet
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => {
                    setActiveExpBulletIdx(idx);
                    setNewBulletText('');
                  }}
                  className="self-start text-[10px] text-indigo-600 hover:text-indigo-800 font-semibold mt-0.5"
                >
                  + Add Bullet Point
                </button>
              )}
            </div>
          ))}
        </div>

        {/* Quick Add Role */}
        <div className="pt-2 border-t border-slate-100 flex flex-col gap-2 text-xs">
          <span className="font-semibold text-slate-700 text-[11px]">+ Add Past or Current Role</span>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="text"
              placeholder="Company (e.g. Google)"
              value={expCompany}
              onChange={(e) => setExpCompany(e.target.value)}
              className="p-1.5 border border-slate-300 rounded text-xs"
            />
            <input
              type="text"
              placeholder="Job Title (e.g. SRE)"
              value={expRole}
              onChange={(e) => setExpRole(e.target.value)}
              className="p-1.5 border border-slate-300 rounded text-xs"
            />
            <input
              type="text"
              placeholder="Start Year (2021)"
              value={expStart}
              onChange={(e) => setExpStart(e.target.value)}
              className="p-1.5 border border-slate-300 rounded text-xs"
            />
            <input
              type="text"
              placeholder="End Year or Present"
              value={expEnd}
              onChange={(e) => setExpEnd(e.target.value)}
              className="p-1.5 border border-slate-300 rounded text-xs"
            />
            <input
              type="text"
              placeholder="Location (e.g. San Francisco or Remote)"
              value={expLocation}
              onChange={(e) => setExpLocation(e.target.value)}
              className="col-span-2 p-1.5 border border-slate-300 rounded text-xs"
            />
          </div>
          <textarea
            rows={2}
            placeholder="Key achievement with metrics (e.g. Scaled API to 10M requests, reduced latency by 35%)..."
            value={expBullet}
            onChange={(e) => setExpBullet(e.target.value)}
            className="p-1.5 border border-slate-300 rounded text-xs resize-none"
          />
          <button
            onClick={handleAddExperience}
            className="w-full py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold rounded text-xs border border-slate-300 transition-colors"
          >
            Add Experience Entry
          </button>
        </div>
      </div>

      {/* 5. Featured Projects Vault */}
      <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col gap-3">
        <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
          5. Featured Projects Vault ({profile.projects?.length || 0})
        </h3>

        {/* Existing Projects */}
        <div className="space-y-3">
          {(profile.projects || []).map((proj, idx) => (
            <div key={idx} className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex flex-col gap-2 text-xs relative group">
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="font-bold text-slate-900 flex items-center gap-1.5">
                    {proj.name}
                    {proj.link && (
                      <span className="text-[10px] font-normal text-indigo-600 bg-indigo-50 px-1 rounded">
                        [{proj.link.includes('github') ? 'GitHub' : 'Link'}]
                      </span>
                    )}
                  </h4>
                  <p className="text-[11px] text-slate-600 font-medium">
                    {proj.subtitle || 'Featured Project'} {proj.technologies && `• ${proj.technologies}`}
                  </p>
                </div>
                <button
                  onClick={() => handleRemoveProject(idx)}
                  className="text-slate-400 hover:text-rose-600 text-xs font-bold p-1"
                  title="Delete project"
                >
                  ✕
                </button>
              </div>

              {/* Project Bullets */}
              <ul className="space-y-1.5 pl-1 text-slate-700 text-[11px]">
                {proj.bullets.map((b, bIdx) => (
                  <li key={bIdx} className="flex items-start gap-1.5 group/bullet">
                    <span className="text-indigo-500 font-bold">•</span>
                    <span className="flex-1 leading-snug">{b.text}</span>
                    <button
                      onClick={() => handleRemoveBulletFromProject(idx, bIdx)}
                      className="opacity-0 group-hover/bullet:opacity-100 text-rose-500 hover:text-rose-700 font-bold text-xs"
                      title="Remove bullet"
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>

              {/* Inline Project Bullet Adder */}
              {activeProjBulletIdx === idx ? (
                <div className="mt-1 flex flex-col gap-1.5 pt-1.5 border-t border-slate-200">
                  <textarea
                    rows={2}
                    placeholder="Enter verified project achievement with metrics..."
                    value={newProjBulletText}
                    onChange={(e) => setNewProjBulletText(e.target.value)}
                    className="p-1.5 border border-slate-300 rounded text-xs resize-none"
                  />
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => setActiveProjBulletIdx(null)}
                      className="px-2 py-1 text-[11px] text-slate-500 hover:text-slate-700 font-semibold"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleAddBulletToProject(idx)}
                      className="px-3 py-1 bg-indigo-600 text-white rounded text-[11px] font-semibold"
                    >
                      Save Bullet
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => {
                    setActiveProjBulletIdx(idx);
                    setNewProjBulletText('');
                  }}
                  className="self-start text-[10px] text-indigo-600 hover:text-indigo-800 font-semibold mt-0.5"
                >
                  + Add Bullet Point
                </button>
              )}
            </div>
          ))}
        </div>

        {/* Quick Add Project */}
        <div className="pt-2 border-t border-slate-100 flex flex-col gap-2 text-xs">
          <span className="font-semibold text-slate-700 text-[11px]">+ Add Technical / Personal Project</span>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="text"
              placeholder="Project Name (e.g. TitanRAG)"
              value={projName}
              onChange={(e) => setProjName(e.target.value)}
              className="p-1.5 border border-slate-300 rounded text-xs"
            />
            <input
              type="text"
              placeholder="Subtitle / Role (e.g. Multi-Tenant RAG)"
              value={projSubtitle}
              onChange={(e) => setProjSubtitle(e.target.value)}
              className="p-1.5 border border-slate-300 rounded text-xs"
            />
            <input
              type="text"
              placeholder="Tech Stack (e.g. Python, FastAPI, Qdrant)"
              value={projTech}
              onChange={(e) => setProjTech(e.target.value)}
              className="p-1.5 border border-slate-300 rounded text-xs"
            />
            <input
              type="text"
              placeholder="Repository / Live URL"
              value={projLink}
              onChange={(e) => setProjLink(e.target.value)}
              className="p-1.5 border border-slate-300 rounded text-xs"
            />
          </div>
          <textarea
            rows={2}
            placeholder="Key accomplishment (e.g. Implemented hybrid vector search with BM25, reaching 94.8% Recall@5)..."
            value={projBullet}
            onChange={(e) => setProjBullet(e.target.value)}
            className="p-1.5 border border-slate-300 rounded text-xs resize-none"
          />
          <button
            onClick={handleAddProject}
            className="w-full py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold rounded text-xs border border-slate-300 transition-colors"
          >
            Add Project Entry
          </button>
        </div>
      </div>

      {/* Education Vault */}
      <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col gap-3">
        <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
          6. Education Vault ({profile.education.length})
        </h3>

        <div className="space-y-2">
          {profile.education.map((edu, idx) => (
            <div key={idx} className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between text-xs">
              <div>
                <h4 className="font-bold text-slate-900">{edu.degree} in {edu.field}</h4>
                <p className="text-[11px] text-slate-600">
                  {edu.institution} • {edu.end_date} {edu.gpa && `• GPA: ${edu.gpa}`}
                </p>
              </div>
              <button
                onClick={() => handleRemoveEducation(idx)}
                className="text-slate-400 hover:text-rose-600 text-xs font-bold p-1"
                title="Remove degree"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        {/* Add Education Form */}
        <div className="pt-2 border-t border-slate-100 flex flex-col gap-2 text-xs">
          <span className="font-semibold text-slate-700 text-[11px]">+ Add University or Degree</span>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="text"
              placeholder="Institution (e.g. Stanford)"
              value={eduInst}
              onChange={(e) => setEduInst(e.target.value)}
              className="p-1.5 border border-slate-300 rounded text-xs"
            />
            <input
              type="text"
              placeholder="Degree (e.g. B.S., M.S.)"
              value={eduDegree}
              onChange={(e) => setEduDegree(e.target.value)}
              className="p-1.5 border border-slate-300 rounded text-xs"
            />
            <input
              type="text"
              placeholder="Field / Major (e.g. CS)"
              value={eduField}
              onChange={(e) => setEduField(e.target.value)}
              className="p-1.5 border border-slate-300 rounded text-xs"
            />
            <input
              type="text"
              placeholder="Graduation Year (2020)"
              value={eduYear}
              onChange={(e) => setEduYear(e.target.value)}
              className="p-1.5 border border-slate-300 rounded text-xs"
            />
          </div>
          <button
            onClick={handleAddEducation}
            className="w-full py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold rounded text-xs border border-slate-300 transition-colors"
          >
            Add Education Entry
          </button>
        </div>
      </div>

      {/* 7. Work Authorization & Screening Preferences */}
      <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col gap-3">
        <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
          7. Work Authorization & Screening Preferences
        </h3>
        <p className="text-[11px] text-slate-500">
          Used by Autopilot and 1-Click Autofill to answer standard application questions accurately.
        </p>

        <div className="grid grid-cols-1 gap-2.5 text-xs">
          <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
            <div>
              <span className="font-semibold text-slate-800">Legally authorized to work in target country?</span>
              <p className="text-[10px] text-slate-500">Common screening question on Workday, Greenhouse & Lever</p>
            </div>
            <div className="flex gap-2">
              <label className="flex items-center gap-1 text-[11px] font-medium cursor-pointer">
                <input
                  type="radio"
                  name="legally_authorized"
                  checked={profile.preferences?.legally_authorized !== false}
                  onChange={() =>
                    setProfile({
                      ...profile,
                      preferences: { ...profile.preferences, legally_authorized: true },
                    })
                  }
                />
                Yes
              </label>
              <label className="flex items-center gap-1 text-[11px] font-medium cursor-pointer">
                <input
                  type="radio"
                  name="legally_authorized"
                  checked={profile.preferences?.legally_authorized === false}
                  onChange={() =>
                    setProfile({
                      ...profile,
                      preferences: { ...profile.preferences, legally_authorized: false },
                    })
                  }
                />
                No
              </label>
            </div>
          </div>

          <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
            <div>
              <span className="font-semibold text-slate-800">Requires visa sponsorship now or in the future?</span>
              <p className="text-[10px] text-slate-500">H-1B, TN, O-1 or other employment visa sponsorship</p>
            </div>
            <div className="flex gap-2">
              <label className="flex items-center gap-1 text-[11px] font-medium cursor-pointer">
                <input
                  type="radio"
                  name="requires_sponsorship"
                  checked={profile.preferences?.requires_sponsorship === true}
                  onChange={() =>
                    setProfile({
                      ...profile,
                      preferences: { ...profile.preferences, requires_sponsorship: true },
                    })
                  }
                />
                Yes
              </label>
              <label className="flex items-center gap-1 text-[11px] font-medium cursor-pointer">
                <input
                  type="radio"
                  name="requires_sponsorship"
                  checked={profile.preferences?.requires_sponsorship !== true}
                  onChange={() =>
                    setProfile({
                      ...profile,
                      preferences: { ...profile.preferences, requires_sponsorship: false },
                    })
                  }
                />
                No
              </label>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 pt-1">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">EEO Gender</label>
              <select
                value={profile.preferences?.gender || 'Decline to self-identify'}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    preferences: { ...profile.preferences, gender: e.target.value },
                  })
                }
                className="w-full p-1.5 border border-slate-300 rounded text-xs bg-white"
              >
                <option value="Decline to self-identify">Decline to state</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Non-Binary">Non-Binary</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Veteran Status</label>
              <select
                value={profile.preferences?.veteran_status || 'I am not a protected veteran'}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    preferences: { ...profile.preferences, veteran_status: e.target.value },
                  })
                }
                className="w-full p-1.5 border border-slate-300 rounded text-xs bg-white"
              >
                <option value="I am not a protected veteran">Not a veteran</option>
                <option value="I identify as a protected veteran">Protected veteran</option>
                <option value="I decline to self-identify">Decline to state</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-0.5">Disability Status</label>
              <select
                value={profile.preferences?.disability_status || 'No, I do not have a disability'}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    preferences: { ...profile.preferences, disability_status: e.target.value },
                  })
                }
                className="w-full p-1.5 border border-slate-300 rounded text-xs bg-white"
              >
                <option value="No, I do not have a disability">No disability</option>
                <option value="Yes, I have a disability">Yes, disability</option>
                <option value="I decline to self-identify">Decline to state</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
