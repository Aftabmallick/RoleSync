import React, { useState } from 'react';

interface TailoredBullet {
  original_bullet_id: string;
  tailored_text: string;
  keywords_emphasized?: string[];
}

interface TailoredExperience {
  company: string;
  role: string;
  dates: string;
  location: string;
  bullet_points: TailoredBullet[];
}

interface MasterBullet {
  id: string;
  text: string;
}

interface MasterExperience {
  company: string;
  role: string;
  bullets: MasterBullet[];
}

interface TailorDiffViewerProps {
  tailoredExperience: TailoredExperience[];
  masterExperience?: MasterExperience[];
}

export const TailorDiffViewer: React.FC<TailorDiffViewerProps> = ({
  tailoredExperience,
  masterExperience = [],
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [viewMode, setViewMode] = useState<'diff' | 'tailored'>('diff');

  // Build a lookup map of original master bullets by ID
  const masterBulletMap: Record<string, string> = {};
  for (const exp of masterExperience) {
    for (const b of exp.bullets || []) {
      masterBulletMap[b.id] = b.text;
    }
  }

  // Count total tailored bullets and keywords emphasized
  let totalBullets = 0;
  const allKeywords = new Set<string>();
  for (const exp of tailoredExperience) {
    for (const b of exp.bullet_points || []) {
      totalBullets++;
      if (b.keywords_emphasized) {
        b.keywords_emphasized.forEach((k) => allKeywords.add(k));
      }
    }
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
      {/* Header bar */}
      <div className="p-3.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-emerald-200" />
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Tailoring Differential & Keywords
          </h3>
          <span className="text-[10px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded font-semibold border border-emerald-200">
            {allKeywords.size} Keywords Emphasized
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="flex bg-slate-200/70 p-0.5 rounded-md text-[10px] font-semibold">
            <button
              onClick={() => setViewMode('diff')}
              className={`px-2 py-0.5 rounded transition-colors ${
                viewMode === 'diff' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Diff View
            </button>
            <button
              onClick={() => setViewMode('tailored')}
              className={`px-2 py-0.5 rounded transition-colors ${
                viewMode === 'tailored' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Tailored Only
            </button>
          </div>
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="text-xs text-slate-400 hover:text-slate-600 p-1"
          >
            {isOpen ? '▲' : '▼'}
          </button>
        </div>
      </div>

      {isOpen && (
        <div className="p-4 flex flex-col gap-4 text-xs">
          {/* Keywords cloud pill strip */}
          {allKeywords.size > 0 && (
            <div className="flex flex-wrap gap-1.5 p-2 bg-slate-50 rounded-lg border border-slate-200/70">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide mr-1 self-center">
                Target Matches:
              </span>
              {Array.from(allKeywords).map((kw, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 bg-indigo-50 text-indigo-700 text-[10px] font-semibold rounded-full border border-indigo-100"
                >
                  ✓ {kw}
                </span>
              ))}
            </div>
          )}

          {/* List of experience entries with bullets */}
          {tailoredExperience.map((exp, expIdx) => (
            <div key={expIdx} className="flex flex-col gap-2.5">
              <div className="flex items-center justify-between border-b border-slate-100 pb-1">
                <span className="font-bold text-slate-800">{exp.role}</span>
                <span className="text-[11px] text-slate-500 font-medium">
                  {exp.company} • {exp.dates}
                </span>
              </div>

              <div className="flex flex-col gap-2">
                {exp.bullet_points.map((b, bIdx) => {
                  const original = masterBulletMap[b.original_bullet_id];
                  const hasKeywords = b.keywords_emphasized && b.keywords_emphasized.length > 0;

                  return (
                    <div
                      key={bIdx}
                      className="p-2.5 rounded-lg border border-slate-100 bg-slate-50/50 flex flex-col gap-1.5"
                    >
                      {viewMode === 'diff' && original && original !== b.tailored_text && (
                        <div className="text-[11px] text-slate-400 line-through pl-2 border-l-2 border-amber-300">
                          {original}
                        </div>
                      )}

                      <div className="text-[11px] text-slate-700 pl-2 border-l-2 border-emerald-500 font-medium leading-relaxed">
                        {b.tailored_text}
                      </div>

                      {hasKeywords && (
                        <div className="flex flex-wrap gap-1 pt-1">
                          {b.keywords_emphasized!.map((kw, kIdx) => (
                            <span
                              key={kIdx}
                              className="text-[9px] font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200"
                            >
                              +{kw}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
