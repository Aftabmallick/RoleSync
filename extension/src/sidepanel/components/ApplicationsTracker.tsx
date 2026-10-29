import React, { useState, useEffect } from 'react';

export interface ApplicationRecord {
  id: string;
  company_name: string;
  job_title: string;
  job_url?: string;
  ats_provider?: string;
  ats_score: number;
  status: 'DRAFT' | 'APPLIED' | 'INTERVIEWING' | 'OFFERED' | 'REJECTED';
  notes?: string;
  applied_at: string;
  updated_at: string;
}

interface ApplicationsTrackerProps {
  apiBaseUrl?: string;
  currentJdToSave?: {
    companyName: string;
    jobTitle: string;
    atsProvider?: string;
    pageUrl?: string;
    score?: number;
  } | null;
  onApplicationSaved?: () => void;
}

export const ApplicationsTracker: React.FC<ApplicationsTrackerProps> = ({
  apiBaseUrl = 'http://localhost:8000/api/v1',
  currentJdToSave,
  onApplicationSaved,
}) => {
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [filter, setFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Manual Add Modal state
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newCompany, setNewCompany] = useState<string>('');
  const [newRole, setNewRole] = useState<string>('');
  const [newUrl, setNewUrl] = useState<string>('');
  const [newScore, setNewScore] = useState<string>('85');
  const [newStatus, setNewStatus] = useState<string>('APPLIED');
  const [newNotes, setNewNotes] = useState<string>('');

  const loadApplications = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/applications`);
      if (res.ok) {
        const data = await res.json();
        setApplications(data.applications || []);
      }
    } catch (e) {
      console.warn('[RoleSync UI] Error fetching applications, falling back to local storage:', e);
      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.get('rolesync_applications', (res) => {
          if (res.rolesync_applications) {
            setApplications(res.rolesync_applications);
          }
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadApplications();
  }, [apiBaseUrl]);

  // Handle Quick Save of current active job
  useEffect(() => {
    if (currentJdToSave) {
      handleSaveJob(
        currentJdToSave.companyName,
        currentJdToSave.jobTitle,
        currentJdToSave.score || 85,
        currentJdToSave.pageUrl || '',
        currentJdToSave.atsProvider || 'GENERIC',
        'Auto-tailored and saved via RoleSync Copilot.'
      );
    }
  }, [currentJdToSave]);

  const handleSaveJob = async (
    company: string,
    role: string,
    score: number,
    url: string,
    provider: string,
    notes: string
  ) => {
    try {
      const payload = {
        company_name: company,
        job_title: role,
        job_url: url,
        ats_provider: provider,
        ats_score: score,
        status: 'APPLIED',
        notes: notes,
      };

      const res = await fetch(`${apiBaseUrl}/applications`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const saved = await res.json();
        setApplications((prev) => [saved, ...prev]);
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
          chrome.storage.local.get('rolesync_applications', (r) => {
            const list = r.rolesync_applications || [];
            chrome.storage.local.set({ rolesync_applications: [saved, ...list] });
          });
        }
        if (onApplicationSaved) onApplicationSaved();
      }
    } catch (e) {
      console.error('[RoleSync UI] Error saving application:', e);
    }
  };

  const handleUpdateStatus = async (appId: string, newStatus: string) => {
    try {
      setApplications((prev) =>
        prev.map((a) => (a.id === appId ? { ...a, status: newStatus as any } : a))
      );

      await fetch(`${apiBaseUrl}/applications/${appId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
    } catch (e) {
      console.error('[RoleSync UI] Error updating application status:', e);
    }
  };

  const handleDelete = async (appId: string) => {
    if (!confirm('Remove this application from your tracker?')) return;
    try {
      setApplications((prev) => prev.filter((a) => a.id !== appId));
      await fetch(`${apiBaseUrl}/applications/${appId}`, {
        method: 'DELETE',
      });
    } catch (e) {
      console.error('[RoleSync UI] Error deleting application:', e);
    }
  };

  const handleCreateManual = async () => {
    if (!newCompany.trim() || !newRole.trim()) return;
    await handleSaveJob(
      newCompany.trim(),
      newRole.trim(),
      parseFloat(newScore) || 80,
      newUrl.trim(),
      'MANUAL',
      newNotes.trim()
    );
    setShowAddModal(false);
    setNewCompany('');
    setNewRole('');
    setNewUrl('');
    setNewNotes('');
  };

  // Stats calculation
  const total = applications.length;
  const interviewing = applications.filter((a) => a.status === 'INTERVIEWING').length;
  const offers = applications.filter((a) => a.status === 'OFFERED').length;
  const avgScore = total > 0 ? Math.round(applications.reduce((acc, a) => acc + (a.ats_score || 0), 0) / total) : 0;

  // Filter & Search
  const filteredApps = applications.filter((a) => {
    const matchesFilter = filter === 'ALL' || a.status === filter;
    const matchesSearch =
      a.company_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.job_title.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'OFFERED':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      case 'INTERVIEWING':
        return 'bg-purple-100 text-purple-800 border-purple-300';
      case 'APPLIED':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      case 'REJECTED':
        return 'bg-rose-100 text-rose-800 border-rose-300';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-300';
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Metrics Banner */}
      <div className="grid grid-cols-4 gap-2 text-center">
        <div className="bg-white p-2.5 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-base font-extrabold text-slate-800">{total}</div>
          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Applied</div>
        </div>
        <div className="bg-white p-2.5 rounded-xl border border-purple-200 shadow-xs">
          <div className="text-base font-extrabold text-purple-700">{interviewing}</div>
          <div className="text-[10px] font-semibold text-purple-600 uppercase tracking-wider">Interview</div>
        </div>
        <div className="bg-white p-2.5 rounded-xl border border-emerald-200 shadow-xs">
          <div className="text-base font-extrabold text-emerald-700">{offers}</div>
          <div className="text-[10px] font-semibold text-emerald-600 uppercase tracking-wider">Offers</div>
        </div>
        <div className="bg-white p-2.5 rounded-xl border border-indigo-200 shadow-xs">
          <div className="text-base font-extrabold text-indigo-700">{avgScore}%</div>
          <div className="text-[10px] font-semibold text-indigo-600 uppercase tracking-wider">Avg ATS</div>
        </div>
      </div>

      {/* Controls & Search */}
      <div className="flex items-center justify-between gap-2">
        <input
          type="text"
          placeholder="Filter by company or role..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 p-1.5 border border-slate-200 rounded-lg text-xs bg-white focus:ring-1 focus:ring-indigo-500"
        />

        <button
          onClick={() => setShowAddModal(true)}
          className="px-2.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs rounded-lg shadow-xs transition-colors whitespace-nowrap"
        >
          + Add Job
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1 text-[11px] font-semibold">
        {['ALL', 'APPLIED', 'INTERVIEWING', 'OFFERED', 'REJECTED'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-2.5 py-1 rounded-full border transition-colors ${
              filter === f
                ? 'bg-indigo-600 text-white border-indigo-600'
                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Application Cards List */}
      <div className="flex flex-col gap-2.5">
        {isLoading ? (
          <div className="p-8 text-center text-xs text-slate-400">Loading applications...</div>
        ) : filteredApps.length === 0 ? (
          <div className="p-8 bg-white rounded-xl border border-dashed border-slate-200 text-center flex flex-col items-center gap-2">
            <span className="text-2xl">📋</span>
            <span className="text-xs font-bold text-slate-700">No applications found</span>
            <p className="text-[11px] text-slate-400 max-w-[220px]">
              Apply to jobs with Copilot or add jobs manually to track your pipeline.
            </p>
          </div>
        ) : (
          filteredApps.map((app) => (
            <div
              key={app.id}
              className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs flex flex-col gap-2 hover:border-slate-300 transition-all"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex flex-col">
                  <h4 className="font-bold text-slate-900 text-xs leading-snug">{app.job_title}</h4>
                  <span className="text-xs font-medium text-slate-600">{app.company_name}</span>
                </div>

                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] font-extrabold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-100">
                    {Math.round(app.ats_score)}%
                  </span>

                  <select
                    value={app.status}
                    onChange={(e) => handleUpdateStatus(app.id, e.target.value)}
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full border cursor-pointer ${getStatusBadge(
                      app.status
                    )}`}
                  >
                    <option value="DRAFT">DRAFT</option>
                    <option value="APPLIED">APPLIED</option>
                    <option value="INTERVIEWING">INTERVIEWING</option>
                    <option value="OFFERED">OFFERED</option>
                    <option value="REJECTED">REJECTED</option>
                  </select>
                </div>
              </div>

              {app.notes && (
                <p className="text-[11px] text-slate-500 bg-slate-50 p-2 rounded border border-slate-100">
                  {app.notes}
                </p>
              )}

              <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-100">
                <span>Applied: {new Date(app.applied_at || Date.now()).toLocaleDateString()}</span>

                <div className="flex items-center gap-2">
                  {app.job_url && (
                    <a
                      href={app.job_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-indigo-600 hover:underline"
                    >
                      View Post ↗
                    </a>
                  )}
                  <button
                    onClick={() => handleDelete(app.id)}
                    className="text-slate-400 hover:text-rose-500 transition-colors"
                    title="Delete Application"
                  >
                    ✕ Delete
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Manual Add Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 p-4 w-full max-w-sm flex flex-col gap-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Add Job to Application Tracker
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600 font-bold"
              >
                ✕
              </button>
            </div>

            <input
              type="text"
              placeholder="Company Name (e.g. Stripe)"
              value={newCompany}
              onChange={(e) => setNewCompany(e.target.value)}
              className="p-2 border border-slate-200 rounded text-xs"
            />
            <input
              type="text"
              placeholder="Job Title (e.g. Senior Backend Engineer)"
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              className="p-2 border border-slate-200 rounded text-xs"
            />
            <input
              type="url"
              placeholder="Job URL (optional)"
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
              className="p-2 border border-slate-200 rounded text-xs"
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                placeholder="ATS Match % (e.g. 88)"
                value={newScore}
                onChange={(e) => setNewScore(e.target.value)}
                className="p-2 border border-slate-200 rounded text-xs"
              />
              <select
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value)}
                className="p-2 border border-slate-200 rounded text-xs bg-white"
              >
                <option value="APPLIED">Status: APPLIED</option>
                <option value="INTERVIEWING">Status: INTERVIEWING</option>
                <option value="OFFERED">Status: OFFERED</option>
                <option value="DRAFT">Status: DRAFT</option>
              </select>
            </div>
            <textarea
              rows={2}
              placeholder="Interview notes, referral contact, or next steps..."
              value={newNotes}
              onChange={(e) => setNewNotes(e.target.value)}
              className="p-2 border border-slate-200 rounded text-xs resize-none"
            />

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-3 py-1.5 text-xs text-slate-600 font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateManual}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs rounded-lg shadow-xs"
              >
                Save Application
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
