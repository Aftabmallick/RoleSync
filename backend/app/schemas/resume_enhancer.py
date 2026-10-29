from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ResumeMatchRequest(BaseModel):
    job_description: str = Field(..., description="Full text of the target job posting")
    target_role: str = Field(..., description="Target job title")
    company_name: str = Field(..., description="Target company name")
    resume: Dict[str, Any] = Field(..., description="Candidate resume profile dictionary")


class SkillAdditionSuggestion(BaseModel):
    name: str
    category: str = "Technical"
    importance: str = "HIGH"  # HIGH, MEDIUM
    reason: str = "Found in job description requirements"


class BulletImprovementSuggestion(BaseModel):
    original_id: str
    company: str
    role: str
    original_text: str
    suggested_text: str
    keywords_added: List[str] = Field(default_factory=list)
    reason: str = "Emphasizes target keywords without fabricating metrics"


class ResumeMatchResponse(BaseModel):
    current_score: Dict[str, Any]
    potential_score: float
    score_boost: float
    matched_skills: List[str]
    missing_skills: List[SkillAdditionSuggestion]
    suggested_summary: Optional[str] = None
    bullet_suggestions: List[BulletImprovementSuggestion]
    missing_keywords: List[str]


class BulletUpdatePayload(BaseModel):
    original_id: str
    suggested_text: str


class ApplyEnhancementsRequest(BaseModel):
    base_resume: Dict[str, Any]
    target_role: str
    company_name: str
    version_name: Optional[str] = None
    accepted_skills: List[str] = Field(default_factory=list)
    accepted_summary: Optional[str] = None
    accepted_bullet_updates: List[BulletUpdatePayload] = Field(default_factory=list)


class ResumeVersionItem(BaseModel):
    id: str
    user_id: str
    name: str
    target_company: str
    target_role: str
    created_at: str
    ats_score: float
    profile_data: Dict[str, Any]
    pdf_base64: Optional[str] = None


class ResumeVersionListResponse(BaseModel):
    total: int
    versions: List[ResumeVersionItem]

