import React from 'react';

export interface ScoreBreakdown {
  composite_score: number;
  semantic_score: number;
  skill_coverage_score: number;
  lexical_score: number;
  experience_alignment_score: number;
  matched_skills?: string[];
  missing_skills?: string[];
  recommendation?: string;
}

interface ScoreCardProps {
  score: ScoreBreakdown;
}

export const ScoreCard: React.FC<ScoreCardProps> = ({ score }) => {
  const getScoreColor = (val: number) => {
    if (val >= 85) return 'text-emerald-600 bg-emerald-50 border-emerald-200';
    if (val >= 70) return 'text-indigo-600 bg-indigo-50 border-indigo-200';
    if (val >= 50) return 'text-amber-600 bg-amber-50 border-amber-200';
    return 'text-rose-600 bg-rose-50 border-rose-200';
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">ATS Composite Score</span>
          <div className="flex items-baseline gap-1 mt-0.5">
            <span className="text-3xl font-extrabold text-slate-900">{score.composite_score}</span>
            <span className="text-sm font-semibold text-slate-400">/ 100</span>
          </div>
        </div>
        <div className={`px-2.5 py-1 rounded-full text-xs font-bold border ${getScoreColor(score.composite_score)}`}>
          {score.composite_score >= 85 ? 'High Pass' : score.composite_score >= 70 ? 'Good Fit' : 'Moderate'}
        </div>
      </div>

      {/* 4-Dimension Metric Bars */}
      <div className="space-y-2 pt-2 border-t border-slate-100">
        <div>
          <div className="flex justify-between text-xs font-medium text-slate-600 mb-1">
            <span>Semantic Embeddings (35%)</span>
            <span className="font-semibold text-slate-800">{score.semantic_score}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div className="bg-indigo-600 h-1.5 rounded-full" style={{ width: `${score.semantic_score}%` }} />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-xs font-medium text-slate-600 mb-1">
            <span>Hard Skill Recall (30%)</span>
            <span className="font-semibold text-slate-800">{score.skill_coverage_score}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div className="bg-emerald-500 h-1.5 rounded-full" style={{ width: `${score.skill_coverage_score}%` }} />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-xs font-medium text-slate-600 mb-1">
            <span>Sublinear Lexical TF (15%)</span>
            <span className="font-semibold text-slate-800">{score.lexical_score}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div className="bg-sky-500 h-1.5 rounded-full" style={{ width: `${score.lexical_score}%` }} />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-xs font-medium text-slate-600 mb-1">
            <span>Seniority Alignment (20%)</span>
            <span className="font-semibold text-slate-800">{score.experience_alignment_score}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div className="bg-amber-500 h-1.5 rounded-full" style={{ width: `${score.experience_alignment_score}%` }} />
          </div>
        </div>
      </div>

      {/* Matched Skills Chips */}
      {score.matched_skills && score.matched_skills.length > 0 && (
        <div className="pt-2 border-t border-slate-100">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">
            Matched Skills
          </span>
          <div className="flex flex-wrap gap-1">
            {score.matched_skills.slice(0, 8).map((skill, idx) => (
              <span key={idx} className="text-[11px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded font-medium">
                ✓ {skill}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
